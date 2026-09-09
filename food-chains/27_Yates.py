import json
from datetime import date
from typing import List, Dict, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from define_collection_wave import folder
from helpers import create_folder

BASE_URL = 'https://tkmenus.com/greattraditionalpubs'
REST_NAME = "Yate's"

path_yates = create_folder('27_Yates', folder)
file_yates_json = path_yates + '/yates_menu.json'
file_yates_csv = path_yates + '/yates_menu.csv'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_text(node) -> Optional[str]:
    if not node:
        return None
    txt = node.get_text(strip=True)
    return txt if txt else None


def get_nutrient_value(block, nutrient_label: str, replace_comma: bool = False) -> Optional[str]:
    nutrient_items = block.select('div.k10-recipe__nutrients-item')
    for n in nutrient_items:
        label_span = n.find('span')
        if not label_span:
            continue
        if nutrient_label in label_span.get_text():
            # value is in following span
            spans = n.find_all('span')
            if len(spans) >= 2:
                val = spans[1].get_text(strip=True)
                if val and replace_comma:
                    val = val.replace(',', '')
                return val
    return None


def parse_menu(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.select('div.k10-l-grid')
    results: List[Dict] = []
    collection_date = date.today().strftime('%b-%d-%Y')

    for item in items:
        section = None
        section_header = item.find_parent('section', class_='k10-course')
        if section_header:
            h2 = section_header.find('h2')
            section = extract_text(h2)

        name = extract_text(item.select_one('span.k10-recipe__name-val'))
        description = extract_text(item.select_one('p.k10-recipe__desc'))
        allergen_labels = [t.strip() for t in item.select_one('div.k10-recipe__labels-wrapper-content').stripped_strings] if item.select_one('div.k10-recipe__labels-wrapper-content') else []

        record = {
            'collection_date': collection_date,
            'rest_name': REST_NAME,
            'menu_section': section,
            'item_name': name,
            'item_description': description,
            'allergens': allergen_labels,
            'kcal': get_nutrient_value(item, 'Energy (kcal)'),
            'kj': get_nutrient_value(item, 'Energy (kJ)', replace_comma=True),
            'protein': get_nutrient_value(item, 'Protein (g)'),
            'carb': get_nutrient_value(item, 'Carbs (g)'),
            'sugar': get_nutrient_value(item, 'Sugars (g)'),
            'fat': get_nutrient_value(item, 'Fat (g)'),
            'satfat': get_nutrient_value(item, 'Saturates (g)'),
            'salt': get_nutrient_value(item, 'Salt (g)')
        }
        results.append(record)
    return results


def crawl_yates_menu():
    try:
        print('Fetching Yates menu page...')
        html = fetch(BASE_URL)
        records = parse_menu(html)
        print(f'Scraped {len(records)} items.')
        
        # Save JSON
        with open(file_yates_json, 'w') as f:
            json.dump(records, f, indent=2)
        
        # Save CSV
        df = pd.DataFrame(records)
        df.to_csv(file_yates_csv, index=False)
        
        print(f'JSON data saved to {file_yates_json}')
        print(f'CSV data saved to {file_yates_csv}')
    except Exception as e:
        print(f'Error during Yates scraping: {e}')


if __name__ == '__main__':
    crawl_yates_menu()
