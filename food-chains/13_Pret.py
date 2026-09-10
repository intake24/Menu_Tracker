# Newer version aims to replace dependency on Scrapy framework
import json
from datetime import date

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from define_collection_wave import folder
from helpers import create_folder, setup_driver

path_pret = create_folder('13_Pret', folder)
file_pret_json = path_pret + '/pret_nutrition.json'
file_pret_csv = path_pret + '/pret_nutrition.csv'


def get_product_urls(driver, category_url):
    """Get all product URLs from a category page"""
    driver.get(category_url)
    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, '//a[@data-testid="product-link"]')))
    return [link.get_attribute('href') for link in driver.find_elements(By.XPATH, '//a[@data-testid="product-link"]')]


def extract_product_data(driver, item_url, category_name):
    """Extract product data from individual product page"""
    driver.get(item_url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//script[@id="__NEXT_DATA__"]')))
    
    text_content = driver.find_element(By.XPATH, '//script[@id="__NEXT_DATA__"]').get_attribute('textContent')
    item_json = json.loads(text_content)['props']['pageProps']['product']
    
    allergens = item_json.get('allergens', [])
    nutrients = item_json.get('nutritionals', [])
    
    item_dict = {
        'rest_name': 'Pret A Manger',
        'collection_date': date.today().strftime("%b-%d-%Y"),
        'item_name': item_json.get('name'),
        'menu_section': category_name,
        'item_description': item_json.get('description'),
        'allergens': [allergen.get('label') for allergen in allergens],
        'ingredients': item_json.get('ingredients'),
        'servingsize': item_json.get('averageWeight'),
        'vegetarian': item_json.get('suitableForVegetarians'),
        'vegan': item_json.get('suitableForVegans'),
        'url': item_url
    }
    
    # Add nutrition data
    for nutrient in nutrients:
        if len(nutrient) >= 3:
            nutrient_name = nutrient[0]['value']
            item_dict[f'{nutrient_name}_100g'] = nutrient[1]['value']
            item_dict[f'{nutrient_name}_perserving'] = nutrient[2]['value']
    
    return item_dict


def process_category(driver, category_url):
    """Process all products in a category"""
    category_name = category_url.split('/')[-1].replace('-', ' ').title()
    print(f"Processing category: {category_name}")
    
    try:
        item_urls = get_product_urls(driver, category_url)
        print(f"Found {len(item_urls)} products in {category_name}")
        
        return [extract_product_data(driver, item_url, category_name) for item_url in item_urls]
    except Exception as e:
        print(f"Error processing category at {category_url}: {str(e)}")
        return []


def crawl_pret_nutrition():
    # Setup driver using helper function
    driver = setup_driver()

    try:
        driver.get("https://www.pret.co.uk/en-GB/our-menu")
        print("Page URL:", driver.current_url)
        print("Page source length:", len(driver.page_source))
        
        # Wait for page to load completely
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'a')))
        
        # Get all links first, then filter like the original Scrapy spider
        all_urls = [link.get_attribute('href') for link in driver.find_elements(By.XPATH, '//a')]
        category_urls = ['https://www.pret.co.uk' + url if url.startswith('/') else url 
                        for url in all_urls if url and 'products/categories' in url]

        print(f"Found {len(all_urls)} total links")
        print(f"Found {len(category_urls)} category URLs")
        print("Sample category URLs:", category_urls[:3] if category_urls else "None found")
        
        # Process all categories and flatten results
        results = [item for category_url in category_urls 
                  for item in process_category(driver, category_url)]
        
        # Save results to JSON file
        with open(file_pret_json, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save results to CSV file
        df = pd.DataFrame(results)
        df.to_csv(file_pret_csv, index=False)
        
        print(f"Scraped {len(results)} items.")
        print(f"JSON data saved to {file_pret_json}")
        print(f"CSV data saved to {file_pret_csv}")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    crawl_pret_nutrition()
