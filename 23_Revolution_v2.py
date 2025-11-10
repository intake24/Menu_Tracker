import json
import logging
from datetime import date
from time import sleep

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains

from define_collection_wave import folder
from helpers import create_folder, setup_driver, clean_text, set_driver_timeouts, try_click_accept_cookies, get_visible_text

path_out = create_folder('23_Revolution', folder)
file_json = path_out + '/revolution_nutrition.json'
file_csv = path_out + '/revolution_nutrition.csv'
REST_NAME = "Revolution"

START_URL = 'https://book.revolution-bars.co.uk/allergens'

logger = logging.getLogger(__name__)

def _safe_click(driver, locator, desc='element', timeout=5):
    logger.debug(f"Attempting safe click on {desc}")
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator))
    try:
        logger.debug(f"Scrolling {desc} into view")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        logger.debug(f"Scroll into view failed for {desc}, continuing...")
        pass
    try:
        ActionChains(driver).move_to_element(el).click().perform()
        logger.debug(f"Clicked on {desc} using ActionChains")
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", el)
            logger.debug(f"Clicked on {desc} using JavaScript")
            return True
        except Exception as e:
            logger.debug(f"JS click failed for {desc}: {e}")
            return False

def _parse_food_item(food_el, cat_name, driver):
    """Extract a single food record from a menu item element.

    Returns a dict record or None if extraction fails.
    """
    try:
        item_name = get_visible_text(
            food_el.find_element(By.XPATH, ".//p[@class='menu-item-title']/strong"),
            driver,
        )
        logger.debug(f"Item name: {item_name}")

        item_description = get_visible_text(
            food_el.find_element(By.XPATH, ".//p[@class='menu-item-description']"),
            driver,
        )
        logger.debug(f"Item description: {item_description}")

        allergens = get_visible_text(
            food_el.find_element(By.XPATH, ".//p[@class='menu-item-contains']"),
            driver,
        )
        logger.debug(f"Item allergens: {allergens}")

        record = {
            'collection_date': date.today().strftime('%b-%d-%Y'),
            'rest_name': REST_NAME,
            'menu_section': cat_name,
            'item_name': item_name,
            'item_description': item_description,
            'allergens': allergens,
        }
        logger.debug(f'Record so far: {record}')
        return record
    except Exception as e:
        logger.error(f"  Error parsing item in category '{cat_name}': {e}")
        return None

def _process_category(cat, idx, total, driver):
    """Open a category element, list its items, and return extracted records."""
    records = []
    try:
        cat_label = get_visible_text(cat, driver)
        logger.info(f'Processing category {idx+1}/{total}: {cat_label}')
        try:
            # Prefer the explicit span title when present
            cat_name = cat.find_element(By.XPATH, ".//h3/span").text or cat_label
        except Exception:
            cat_name = cat_label or 'Unknown'

        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", cat)
        except Exception:
            pass
        try:
            driver.execute_script("arguments[0].click();", cat)
        except Exception:
            logger.error(f"Cannot click food category {cat_label}, skipping...")
            return records

        # Gather food items within this category
        food_items_xpath = ".//div[@class='menu-item-card']"
        food_els = cat.find_elements(By.XPATH, food_items_xpath)
        logger.info(f'Found {len(food_els)} food items.')
        for food_idx, food_el in enumerate(food_els):
            logger.info(f' Processing item {food_idx+1}/{len(food_els)}')
            rec = _parse_food_item(food_el, cat_name, driver)
            if rec:
                records.append(rec)
                logger.info(f"Processed {food_idx+1}/{len(food_els)}: {rec.get('item_name','')} ")
        return records
    except Exception as e:
        logger.error(f"Error processing category {idx+1}: {e}")
        return records

def crawl_nutrition():
    driver = setup_driver()
    set_driver_timeouts(driver)
    
    results = []
    try:
        driver.get(START_URL)
        logger.info(f'Page URL: {driver.current_url}')
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, 'onetrust-banner-sdk'))
            )
            logger.info("Cookie banner detected, attempting to accept...")
            try_click_accept_cookies(driver)
            sleep(1)
        except TimeoutException:
            logger.info("No cookie banner detected.")
            pass

        # Declaration Page: match button labelled ACCEPT or anchor by visible text (case-insensitive)
        logger.info('Waiting for Declaration screen to load...')
        decl_locator = (
            By.XPATH,"//div[@class='rbg-modal rbg-modal--full-page']//button[@class='btn']"
        )
        WebDriverWait(driver, 5).until(EC.presence_of_element_located(decl_locator))
        logger.info('Declaration screen detected.')
        # Try click robustly
        if not _safe_click(driver, decl_locator, desc='declaration'):
            logger.error("Cannot click declaration button to proceed, quitting...")
            driver.quit()
            return

        # Wait for location selector to load
        logger.info('Waiting for location selector to load...')
        location_xpath = "//div[contains(@class,'bar-select')]"
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.XPATH, location_xpath))
        )
        WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH, location_xpath))
        )
        logger.info('Location selector loaded and clickable.')
        if not _safe_click(driver, (By.XPATH, location_xpath), desc='location select'):
            logger.error("Cannot click location bar to get a bar, quitting...")
            driver.quit()
            return
        logger.debug("Selecting location")

        # Pick the first location to proceed
        location_selection_xpath = (
            "(//div[contains(@class,'css-26l3qy-menu')]//div[@id and contains(@id,'react-select') and contains(@id,'-option-')])[1]"
        )
        logger.debug(f"Waiting for location options to load, xpath: {location_selection_xpath}")
        WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH, location_selection_xpath))
        )
        el = driver.find_element(By.XPATH, location_selection_xpath)
        location_name = get_visible_text(el, driver)
        logger.info(f'Trying to select location {location_name}...')
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass
        try:
            driver.execute_script("arguments[0].click();", el)
        except Exception:
            if not _safe_click(driver, (By.XPATH, location_selection_xpath), desc='location option'):
                logger.error("Cannot click location option, quitting...")
                driver.quit()
                return
        logger.debug(f"Selected location:{location_name}")


        # Wait for the food menu select container to be present
        logger.info('Waiting for food menu selector to load...')
        menu_container_xpath = "(//div[contains(@class,' css-2b097c-container')])[2]"
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.XPATH, menu_container_xpath))
        )

        if not _safe_click(driver, (By.XPATH, menu_container_xpath), desc='menu select'):
            logger.error("Cannot click menu to get items, quitting...")
            driver.quit()
            return
        # Pick the first menu to count number of menus
        logger.debug("Selecting menu items")
        menu_item_xpath = (
            "//div[contains(@class,'css-26l3qy-menu')]//div[@id and contains(@id,'react-select') and contains(@id,'-option-')]"
        )
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.XPATH, menu_item_xpath))
        )
        menu_els = driver.find_elements(By.XPATH, menu_item_xpath)
        logger.info(f'Found {len(menu_els)} menu sections.')

        # click to reset menu container
        if not _safe_click(driver, (By.XPATH, menu_container_xpath), desc='menu select'):
            logger.error("Cannot click menu to get items, quitting...")
            driver.quit()
            return

        for idx in range(len(menu_els)):
            
            logger.info('Looping for menus: waiting for food menu selector to load...')
            menu_container_xpath = "(//div[contains(@class,' css-2b097c-container')])[2]"
            WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.XPATH, menu_container_xpath))
            )

            if not _safe_click(driver, (By.XPATH, menu_container_xpath), desc='menu select'):
                logger.error("Cannot click menu to get items, quitting...")
                driver.quit()
                return
            # Pick the first menu dynamically rather than hard-coded index
            logger.debug("Selecting menu items")
            menu_item_xpath = (
                "(//div[contains(@class,'css-26l3qy-menu')]//div[@id and contains(@id,'react-select') and contains(@id,'-option-')])["+str(idx + 1)+"]"
            )
            logger.debug(f"Waiting for menu options to load, xpath: {menu_item_xpath}")
            WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.XPATH, menu_item_xpath))
            )
            menu_el = driver.find_element(By.XPATH, menu_item_xpath)
            menu_name = get_visible_text(menu_el, driver)
            logger.info(f'Trying to select menu {menu_name}...')
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", menu_el)
            except Exception:
                pass
            try:
                driver.execute_script("arguments[0].click();", menu_el)
            except Exception:
                if not _safe_click(driver, (By.XPATH, menu_item_xpath), desc='menu option'):
                    logger.error("Cannot click menu item to get items, quitting...")
                    driver.quit()
                    return
            logger.info(f"Selected menu:{menu_name}, wait 5 seconds...")
            sleep(5)
            # Wait for food category to load
            food_cats_xpath = "//ul[contains(@class, 'allergens-menu-list-menu-items')]"
            WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.XPATH, food_cats_xpath))
            )
            food_el = driver.find_element(By.XPATH, food_cats_xpath)
            logger.info('Food categories loaded.')
            logger.info(f'Finding food categories...')
            cats = food_el.find_elements(By.XPATH, ".//li")
            logger.info(f'Found {len(cats)} food categories')
            for idx, cat in enumerate(cats):
                records = _process_category(cat, idx, len(cats), driver)
                if records:
                    results.extend(records)



        # Save outputs
        with open(file_json, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Scraped {len(results)} items. Data saved to {file_json}.")

        if results:
            pd.DataFrame(results).to_csv(file_csv, index=False)
            logger.info(f"Data also saved to CSV: {file_csv}")
    # except TimeoutException:
    #     logger.info('Timed out waiting for menu items.')
    except Exception as e:
        logger.info(f'Error during scraping: {e}')
    finally:
        driver.quit()


if __name__ == '__main__':
    crawl_nutrition()

