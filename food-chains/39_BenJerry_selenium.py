import json
import os
import re
import shutil
import subprocess
import time
from datetime import date
from urllib.parse import urljoin

import pandas as pd
import requests
from lxml import html

from define_collection_wave import folder
from helpers import create_folder, setup_driver, set_driver_timeouts

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

BASE_URL = 'https://www.benjerry.co.uk/flavours'
HOST = 'https://www.benjerry.co.uk'
REST_NAME = "Ben & Jerry's"

path_benjerry = create_folder('39_BenJerry', folder)


def try_click(driver, xpaths, timeout=5):
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            btn.click()
            return True
        except Exception:
            continue
    return False


def accept_cookies_if_present(driver, timeout=2):
    """Use short timeout so we don't block when banner is absent or has different text."""
    xpaths = [
        "//button[contains(., 'Accept')]",
        "//button[contains(., 'I Accept')]",
        "//button[contains(., 'Agree')]",
        "//button[contains(., 'Allow all')]",
        "//button[contains(., 'allow all')]",
    ]
    try_click(driver, xpaths, timeout=timeout)


def get_url(driver, url):
    """Navigate to url; on page-load timeout stop loading and proceed (avoids indefinite hang).
    Prints the time taken by the function.
    """
    start_time = time.time()
    try:
        driver.get(url)
    except TimeoutException:
        try:
            driver.execute_script("window.stop();")
        except Exception:
            pass
    end_time = time.time()
    # print(f"get_url: Time used: {end_time - start_time:.2f} seconds")


def get_text_or_empty(driver, by, selector):
    try:
        return driver.find_element(by, selector).text.strip()
    except NoSuchElementException:
        return ''


def ocr_image(url):
    if not url or not shutil.which('tesseract'):
        return ''
    url = re.sub(r'imwidth=\d+', 'imwidth=2400', url)
    response = requests.get(
        url,
        headers={'User-Agent': 'Mozilla/5.0', 'Referer': HOST + '/'},
        timeout=30,
    )
    response.raise_for_status()
    result = subprocess.run(
        ['tesseract', 'stdin', 'stdout', '--psm', '11'],
        input=response.content,
        capture_output=True,
        timeout=30,
    )
    return result.stdout.decode(errors='replace').strip() if result.returncode == 0 else ''


def _accordion_text(driver, button_texts, timeout=2):
    """Click first matching accordion button and return following-sibling div text."""
    for text in button_texts:
        try:
            # Verify if a button with any of the texts in button_texts exists before attempting to click
            button_found = False
            for btn_text in button_texts:
                xp = f"//button[contains(., '{btn_text}')]"
                try:
                    driver.find_element(By.XPATH, xp)
                    button_found = True
                    break
                except NoSuchElementException:
                    continue
            if not button_found:
                continue
            print(f"Expanding accordion: {text}")
            try_click(driver, [f"//button[contains(., '{text}')]"], timeout=timeout)
            el = driver.find_element(
                By.XPATH,
                f"//button[contains(., '{text}')]/parent::h3/following-sibling::div"
            )
            return el.text.replace(f"{text}:", "").strip()
        except NoSuchElementException:
            continue
    return ''


def parse_product_page(driver):
    # Ensure title exists (short wait; page may have timed out)
    try:
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.TAG_NAME, 'h1'))
        )
    except TimeoutException:
        pass

    product_name = get_text_or_empty(driver, By.TAG_NAME, 'h1')
    if product_name:
        print(f"  Parsing product page for: {product_name}")
    else:
        print("  Parsing product page with missing <h1> title")

    # Description
    try:
        desc_el = driver.find_element(By.XPATH, "//section[@class='flavor-about']/div")
        product_description = desc_el.text.strip()
    except NoSuchElementException:
        product_description = ''

    # Expand Ingredients accordion if needed, then extract text and image
    ingredients = ''
    ingredient_image = ''
    try:
        try_click(driver, ["//button[contains(., 'Ingredients')]"], timeout=2)
        try:
            ing_el = driver.find_element(By.XPATH, "//button[contains(., 'Ingredients')]/parent::h3/following-sibling::div")
            ingredients = ing_el.text.replace('Ingredients:', '').strip()
        except NoSuchElementException:
            ingredients = ''
        try:
            img_el = driver.find_element(By.XPATH, "//button[contains(., 'Ingredients')]/parent::h3/following-sibling::div//img")
            src = img_el.get_attribute('src') or ''
            if src:
                ingredient_image = urljoin(HOST + '/', src)
        except NoSuchElementException:
            ingredient_image = ''
    except Exception:
        pass

    # Nutrition and allergens (accordion sections)
    nutrition_info = _accordion_text(
        driver,
        ['Nutritional information', 'Nutrition', 'Nutrition information'],
        timeout=2
    )
    allergens = _accordion_text(
        driver,
        ['Allergen', 'Allergens', 'Allergy information'],
        timeout=2
    )
    nutrition_image = ''
    try:
        image = driver.find_element(
            By.XPATH,
            "//img[contains(@alt,'Nutrition Facts') or contains(@src,'Nutritional')]",
        )
        nutrition_image = image.get_attribute('src') or ''
        if not nutrition_info:
            nutrition_info = ocr_image(nutrition_image)
    except Exception:
        pass
    if not allergens and ingredients:
        # Fallback: "May contain: X, Y" in ingredients
        m = re.search(r'[Mm]ay contain[:\s]+([^.>]+)', ingredients)
        if m:
            allergens = m.group(1).strip()

    return product_name, product_description, ingredients, ingredient_image, nutrition_image, nutrition_info, allergens


def crawl_ben_jerry_selenium(quick_test=False):
    print(f"Starting Ben & Jerry's Selenium crawl at {BASE_URL}")
    driver = setup_driver()
    set_driver_timeouts(driver)
    try:
        driver.set_page_load_timeout(15)
    except Exception:
        pass
    data_store = []
    try:
        get_url(driver, BASE_URL)
        print("Loaded base flavours page")
        accept_cookies_if_present(driver)
        print("Cookie banner handled (if present)")

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_all_elements_located((By.XPATH, "//section//a[contains(., 'View All')]"))
            )
        except TimeoutException:
            pass

        cat_links = [a.get_attribute('href') for a in driver.find_elements(By.XPATH, "//section//a[contains(., 'View All')]")]
        cat_links = [l for l in cat_links if l]
        if quick_test:
            cat_links = cat_links[:1]
        print(f"Found {len(cat_links)} category links")

        for idx_cat, cat_url in enumerate(cat_links, start=1):
            print(f"\n[{idx_cat}/{len(cat_links)}] Visiting category: {cat_url}")
            get_url(driver, cat_url)
            try:
                WebDriverWait(driver, 12).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".flavor-card a"))
                )
            except TimeoutException:
                pass

            category_name = get_text_or_empty(driver, By.TAG_NAME, 'h1')
            print(f"  Category title: {category_name or 'UNKNOWN'}")

            product_links = [a.get_attribute('href') for a in driver.find_elements(By.CSS_SELECTOR, '.flavor-card a')]
            product_links = [l for l in product_links if l]
            if quick_test:
                product_links = product_links[:2]
            print(f"  Found {len(product_links)} product links in this category")

            for idx_prod, prod_url in enumerate(product_links, start=1):
                print(f"    [{idx_prod}/{len(product_links)}] Visiting product: {prod_url}")
                get_url(driver, prod_url)
                name, desc, ing, ing_img, nutrition_image, nutrition_info, allergens = parse_product_page(driver)

                record = {
                    'collection_date': date.today().strftime('%b-%d-%Y'),
                    'rest_name': REST_NAME,
                    'category_name': category_name,
                    'product_name': name,
                    'product_description': desc,
                    'ingredients': ing,
                    'ingredient_image': ing_img,
                    'nutrition_image': nutrition_image,
                    'nutrition_info': nutrition_info,
                    'allergens': allergens,
                }
                data_store.append(record)

    finally:
        print("Closing Selenium driver")
        driver.quit()

    # Write once at end
    df = pd.DataFrame(data_store)
    out_file = os.path.join(path_benjerry, '39_BenJerry_items.csv')
    with open(os.path.join(path_benjerry, '39_BenJerry_items.json'), 'w') as file:
        json.dump(data_store, file, indent=2)
    df.to_csv(out_file, index=False)

    print(f"Scraped {len(data_store)} items. Data saved to {out_file}")


if __name__ == '__main__':
    quick = os.environ.get('BENJERRY_QUICK_TEST', '').lower() in ('1', 'true', 'yes')
    crawl_ben_jerry_selenium(quick_test=quick)
