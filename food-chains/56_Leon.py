import os
import json
from datetime import date
from typing import Dict, List

import requests
import pandas as pd
from lxml import html

from define_collection_wave import folder
from helpers import create_folder, setup_driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_DOMAIN = 'https://leon.co'
REST_NAME = 'Leon'

# Leon menu category URLs
MENU_URLS = [
    'https://leon.co/menu/all-day/',
    'https://leon.co/menu/bits-in-between/',
    'https://leon.co/menu/breakfast/',
    'https://leon.co/menu/coffee/',
    'https://leon.co/menu/drinks/',
    'https://leon.co/menu/kids/',
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Outputs
path_out = create_folder('56_Leon', folder)
file_json = os.path.join(path_out, 'leon_items.json')
file_csv = os.path.join(path_out, 'leon_items.csv')


def get_item_links_from_category(category_url: str) -> List[str]:
    """Use Selenium to get item links from a category page."""
    driver = setup_driver()
    try:
        driver.get(category_url)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.menu-grid__item'))
        )
        
        # Get all menu item links
        elements = driver.find_elements(By.CSS_SELECTOR, 'a.menu-grid__item')
        links = []
        for elem in elements:
            href = elem.get_attribute('href')
            if href:
                # Convert relative URLs to absolute
                if href.startswith('/'):
                    href = BASE_DOMAIN + href
                links.append(href)
        
        return links
    finally:
        driver.quit()


def fetch(url: str) -> str:
    """Fetch HTML content from URL using requests."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_item_page(html_text: str, item_url: str) -> Dict:
    """Parse individual item page to extract nutrition and details."""
    sc = html.fromstring(html_text)
    
    # Basic item info
    item_name = sc.xpath('normalize-space(//div[@class="menu-item__main-info"]/div/h1/text())')
    
    # Description - handle potential whitespace/newlines
    description_parts = sc.xpath('//div[@class="menu-item__main-info"]/div/p[@class="p-top p-btm"]/text()')
    item_description = ' '.join(part.strip() for part in description_parts if part.strip())
    
    # Allergens
    allergens_list = sc.xpath('//div[@class="menu-item-allergens"]//div[@class="pill  "]/text()')
    allergens = ', '.join(allergens_list) if allergens_list else ''
    
    # Ingredients
    ingredients = sc.xpath('normalize-space(//div[@class="menu-item__ingredients"]/p/text())')
    
    # Nutrition data
    nutrition_dict = {}
    nutrition_rows = sc.xpath('//div[@class="menu-item__nutrition__item"]')
    for row in nutrition_rows:
        header = row.xpath('normalize-space(.//p[@class="small"]/b/text())')
        value = row.xpath('normalize-space(.//p[@class="small text-right"]/text())')
        if header and value:
            nutrition_dict[header] = value
    
    # Determine menu section from URL
    menu_section = ''
    for category_url in MENU_URLS:
        if category_url.replace('https://leon.co/menu/', '').replace('/', '') in item_url:
            menu_section = category_url.replace('https://leon.co/menu/', '').replace('/', '').replace('-', ' ').title()
            break
    
    record = {
        'collection_date': date.today().strftime('%b-%d-%Y'),
        'rest_name': REST_NAME,
        'menu_section': menu_section,
        'item_name': item_name or '',
        'item_description': item_description or '',
        'allergens': allergens,
        'ingredients': ingredients or '',
    }
    
    # Add nutrition data
    record.update(nutrition_dict)
    
    return record


def crawl_leon():
    """Main crawling function."""
    all_records: List[Dict] = []
    
    # Get all item links from each category
    all_item_links = []
    for category_url in MENU_URLS:
        try:
            print(f"Getting items from: {category_url}")
            links = get_item_links_from_category(category_url)
            all_item_links.extend(links)
            print(f"Found {len(links)} items in category")
        except Exception as e:
            print(f"Failed to get items from {category_url}: {e}")
    
    # Remove duplicates
    unique_links = list(set(all_item_links))
    print(f"Total unique items to process: {len(unique_links)}")
    
    # Process each item
    for item_url in unique_links:
        try:
            print(f"Processing: {item_url}")
            html_text = fetch(item_url)
            record = parse_item_page(html_text, item_url)
            all_records.append(record)
        except Exception as e:
            print(f"Failed to process {item_url}: {e}")
    
    # Save outputs
    with open(file_json, 'w') as f:
        json.dump(all_records, f, indent=2)
    
    try:
        pd.DataFrame(all_records).to_csv(file_csv, index=False)
    except Exception as e:
        print(f'CSV export failed: {e}')
    
    print(f'Scraped {len(all_records)} items from {len(unique_links)} URLs.')
    print(f'Saved: {file_json}')
    print(f'Saved: {file_csv}')


if __name__ == '__main__':
    crawl_leon()