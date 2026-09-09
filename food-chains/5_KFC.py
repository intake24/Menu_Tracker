# Newer version aims to replace dependency on Scrapy framework
import json
from datetime import date

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from define_collection_wave import folder
from helpers import create_folder, setup_driver, set_driver_timeouts, try_click_accept_cookies

path_out = create_folder('5_KFC', folder)
file_json = path_out + '/kfc_nutrition.json'
file_csv = path_out + '/kfc_nutrition.csv'
REST_NAME = "KFC"

START_URL = "https://www.kfc.co.uk/nutrition-allergens?close"
script_data_xpath_expr = "//script[@id='__NEXT_DATA__']"


def crawl_nutrition():
    # Setup driver using helper function
    driver = setup_driver()
    set_driver_timeouts(driver)
    try_click_accept_cookies(driver)

    try:
        driver.get(START_URL)
        
        # Print page source to see what's actually loaded
        print("Page URL:", driver.current_url)
        print("Page source length:", len(driver.page_source))
        # print("First 1000 characters of page source:")
        # print(driver.page_source[:1000])
        
        # Wait for the script tag to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, script_data_xpath_expr))
        )
        text_content = driver.find_element(By.XPATH, script_data_xpath_expr).get_attribute('textContent')
        print("Text content found, length:", len(text_content))
        print("First 200 characters of text content:")
        print(text_content[:200])
        dat = json.loads(text_content)
        items = dat.get('props').get('pageProps').get('data').get('mainContent')[2].get('data').get("children").get("products")
        results = []
        for item in items:
            allergens = item.get('allergens')
            allergen_list = [allergen for allergen in allergens.keys() if allergens.get(allergen).get('type') is not False]
            nutrients = item.get('nutrition')
            vegan = item.get('vegan')
            vegetarian = item.get('vegetarian')
            item_dict = {
                'rest_name': REST_NAME,
                'collection_date': date.today().strftime("%b-%d-%Y"),
                'item_name': item.get('name'),
                'menu_section': item.get('categories')[0],
                'allergens': allergen_list,
                'vegan': vegan,
                'vegetarian': vegetarian
            }
            item_dict.update(nutrients)
            results.append(item_dict)
        
        # Save results to JSON file
        with open(file_json, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save results to CSV file
        df = pd.DataFrame(results)
        df.to_csv(file_csv, index=False)
        
        print(f"Scraped {len(results)} items.")
        print(f"JSON data saved to {file_json}")
        print(f"CSV data saved to {file_csv}")
    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_nutrition()

