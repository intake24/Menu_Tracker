import json
from datetime import date
from time import sleep

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from define_collection_wave import folder
from helpers import create_folder, setup_driver, clean_text

path_revolution = create_folder('23_Revolution', folder)
file_revolution_json = path_revolution + '/revolution_nutrition.json'
file_revolution_csv = path_revolution + '/revolution_nutrition.csv'

START_URL = 'https://www.revolution-bars.co.uk/bar/cambridge/menus/food-menu'


def crawl_revolution_nutrition():
    driver = setup_driver()
    results = []
    try:
        driver.get(START_URL)
        print('Page URL:', driver.current_url)
        print('Waiting for menu items to load...')
        WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class,'menusitem')]") )
        )
        sleep(0.5)
        print('Menu items loaded.')

        def get_items():
            return driver.find_elements(By.XPATH, "//*[@class='menusitem']")

        items = get_items()
        print(f'Found {len(items)} menu items')

        for idx in range(len(items)):
            try:
                items = get_items()  # refetch to avoid stale refs after DOM changes
                if idx >= len(items):
                    break
                item_el = items[idx]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", item_el)
                sleep(0.2)

                # Click nutrition icon inside this item (if exists)
                try:
                    nutrition_icon = item_el.find_element(By.XPATH, ".//li[contains(@class,'menusitem__title__icon--nutrition')]")
                    driver.execute_script("arguments[0].click();", nutrition_icon)
                    sleep(0.4)
                except Exception:
                    print(f"Item {idx+1}: no nutrition icon; skipping nutrition details")

                # Re-select current item element after possible expansion
                items = get_items()
                if idx >= len(items):
                    continue
                item_el = items[idx]

                def safe_text(xpath, default=""):
                    try:
                        return clean_text(item_el.find_element(By.XPATH, xpath).text)
                    except Exception:
                        return default

                item_name = safe_text(".//p/strong", "Unknown")
                item_description = safe_text(".//div[contains(@class,'desc')]")
                price = safe_text(".//p[@class='price']")
                allergens = safe_text(".//div[contains(@class,'font--mediumgrey') and contains(@class,'font--italic')]")

                # Nutrition labels/values within this item only
                labels = [clean_text(e.text) for e in item_el.find_elements(By.XPATH, ".//div[@class='menusitem__nutrition-title']")]
                values = [clean_text(e.text) for e in item_el.find_elements(By.XPATH, ".//div[@class='menusitem__nutrition-value']")]
                nutrient_pairs = dict(zip(labels, values)) if labels and values else {}

                menu_section = driver.current_url.rstrip('/').split('/')[-2] if '/' in driver.current_url else 'Unknown'

                record = {
                    'collection_date': date.today().strftime('%b-%d-%Y'),
                    'rest_name': 'Revolution Vodka Bars',
                    'menu_section': menu_section,
                    'item_name': item_name,
                    'item_description': item_description,
                    'price': price,
                    'allergens': allergens
                }
                record.update(nutrient_pairs)
                results.append(record)
                print(f"Processed {idx+1}/{len(get_items())}: {item_name}")
            except Exception as e:
                print(f"Error processing item {idx+1}: {e}")
                continue

        # Save outputs
        with open(file_revolution_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Scraped {len(results)} items. Data saved to {file_revolution_json}.")

        if results:
            pd.DataFrame(results).to_csv(file_revolution_csv, index=False)
            print(f"Data also saved to CSV: {file_revolution_csv}")
    except TimeoutException:
        print('Timed out waiting for menu items.')
    except Exception as e:
        print(f'Error during scraping: {e}')
    finally:
        driver.quit()


if __name__ == '__main__':
    crawl_revolution_nutrition()
