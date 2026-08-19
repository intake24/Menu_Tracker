"""
Marstons Menu Scraper - Converted from Scrapy to standalone Python

This script scrapes menu data from a Marstons restaurant page using Selenium.
The target site is dynamic and requires a browser to render menu content.

Note: As of September 2025, the original Marstons menu URL 
(https://menus.tenkites.com/marstons/communityfood11) returns 404 Not Found.
The menu may have been moved or discontinued. Check https://www.marstons.co.uk
for current menu information.

Dependencies:
- selenium: Browser automation
- pandas: CSV export
- define_collection_wave: Output folder management
- helpers: Utility functions
"""

import os
import time
import json
from datetime import date
from typing import Dict, List

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from define_collection_wave import folder
from helpers import create_folder, setup_driver, clean_text

BASE_URL = 'https://www.dragonflypubbasingstoke.co.uk/menus'
REST_NAME = 'Marstons'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Outputs
path_out = create_folder('60_Marstons', folder)
file_json = os.path.join(path_out, 'marstons_items.json')
file_csv = os.path.join(path_out, 'marstons_items.csv')


def get_nutrition_data(item_el) -> Dict[str, str]:
    """Extracts nutrition data from an expanded item."""
    nutrition_data = {}
    try:
        # It is not necessary to click and the data is already in the DOM
        # nutrition_rows = WebDriverWait(driver, 2).until(
        #     EC.visibility_of_all_elements_located((By.XPATH, ".//div[contains(@class, 'Icons_nutritionTable')]/div"))
        # )
        nutrition_rows = item_el.find_elements(By.XPATH, ".//div[contains(@class, 'Icons_nutritionTable')]/div")
        for row in nutrition_rows:
            try:
                key = row.find_element(By.XPATH, "./div[1]").get_attribute('textContent')
                value = row.find_element(By.XPATH, "./div[2]").get_attribute('textContent')
                if key and value:
                    nutrition_data[key] = value
            except NoSuchElementException:
                continue
    except TimeoutException:
        print("    - No nutrition data found for this item.")
    return nutrition_data


def process_menu(driver, menu_button) -> List[Dict]:
    """Clicks a menu tab and scrapes all items within it."""
    all_items = []
    menu_name = clean_text(menu_button.get_attribute('textContent'))
    print(f"\nProcessing menu: {menu_name}")

    # Click the menu button to show its content
    driver.execute_script("arguments[0].click();", menu_button)
    time.sleep(1) # Wait for content to switch

    try:
        # Wait for the categories (h2) to be present for this menu
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'TenKitesMenuBlock_categories')]//h2"))
        )
        print(f"  - Found categories for menu '{menu_name}'.")
    except TimeoutException:
        print(f"  - No categories found for menu '{menu_name}'. Skipping.")
        return []

    # Items render progressively after the category headers appear; wait for
    # the count to stop growing instead of grabbing the first (partial) snapshot.
    item_selector = "//div[contains(@class, 'Item_item__')]"
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, item_selector))
    )
    previous_count = -1
    for _ in range(10):
        item_elements = driver.find_elements(By.XPATH, item_selector)
        if len(item_elements) == previous_count:
            break
        previous_count = len(item_elements)
        time.sleep(0.5)
    print(f"  Found {len(item_elements)} potential items in '{menu_name}'.")

    for item_el in item_elements:
        try:
            # Basic info
            item_name = clean_text(item_el.find_element(By.XPATH, ".//h5").get_attribute('textContent'))
            if item_name:
                print(f"    - Found item {item_name}")
            else:
                print("    - No item name found; skipping.")
                continue

            # Safely get description, as some items may not have one
            try:
                item_description = clean_text(item_el.find_element(By.XPATH, ".//p").get_attribute('textContent'))
            except NoSuchElementException:
                item_description = ""
            print(f"      Description: {item_description}")
            # Find the category name (the preceding h2)
            category_name = clean_text(item_el.find_element(By.XPATH, "./preceding::h2[1]").get_attribute('textContent'))
            print(f"      Category: {category_name}")

            record = {
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'rest_name': REST_NAME,
                'menu_name': menu_name,
                'menu_section': category_name,
                'item_name': item_name,
                'item_description': item_description,
            }

            # Click nutrition icon to expand details
            try:
                nutrition_icon = item_el.find_element(By.XPATH, ".//button[contains(@class, 'Icons_icon')]")
                
                # Uncommenting the click is optional; data is already in DOM
                # driver.execute_script("arguments[0].click();", nutrition_icon)
                # print("      (Clicked nutrition icon.)")
                # time.sleep(0.5) # Wait for animation

                # Get nutrition data from the now-visible element
                nutrition_data = get_nutrition_data(item_el)
                record.update(nutrition_data)

            except NoSuchElementException:
                print(f"    - No nutrition icon for '{item_name}'")

            all_items.append(record)
            print(f"    - Scraped: {item_name}")

        except Exception as e:
            print(f"    - Error processing an item: {e}")
            continue

    return all_items


def save_data(items: List[Dict]) -> None:
    """Save scraped data to JSON and CSV files."""
    print(f'\nSaving {len(items)} items...')

    # Save to JSON
    with open(file_json, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    print(f'Saved JSON to: {file_json}')

    # Save to CSV
    if items:
        df = pd.DataFrame(items)
        df.to_csv(file_csv, index=False, encoding='utf-8')
        print(f'Saved CSV to: {file_csv}')
    else:
        # Create empty files if no data was scraped
        open(file_csv, 'w').close()
        print('No items found; created empty CSV.')


def crawl_marstons():
    """Main function to crawl Marstons menu."""
    driver = setup_driver()
    all_records = []
    try:
        driver.get(BASE_URL)
        # Handle cookies
        try:
            cookie_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "ccc-notify-accept"))
            )
            cookie_button.click()
            print("Accepted cookies.")
            time.sleep(1)
        except TimeoutException:
            print("Cookie banner not found or not clickable.")

        # Find all menu selection buttons
        menu_buttons = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, '//button[contains(@class, "TenKitesMenuBlock_menuSelect")]'))
        )
        print(f"Found {len(menu_buttons)} menus to process.")

        # Iterate through each menu button, click it, and scrape the content
        for i in range(len(menu_buttons)):
            # Re-find buttons each loop to avoid stale element references
            buttons = driver.find_elements(By.XPATH, '//button[contains(@class, "TenKitesMenuBlock_menuSelect")]')
            if i < len(buttons):
                items = process_menu(driver, buttons[i])
                all_records.extend(items)

    except Exception as e:
        print(f'Unexpected error during scraping: {e}')

    finally:
        save_data(all_records)
        driver.quit()
        print(f'\nScraping completed. Total items: {len(all_records)}')


if __name__ == '__main__':
    # Run the scraper
    crawl_marstons()