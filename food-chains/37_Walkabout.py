import json
import os
from datetime import date
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder

BASE_URL = 'http://tkmenus.com/walkabout/'
REST_NAME = 'Walkabout'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Outputs
path_out = create_folder('37_Walkabout', folder)
file_json = os.path.join(path_out, 'walkabout_items.json')
file_csv = os.path.join(path_out, 'walkabout_items.csv')


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def text(node) -> Optional[str]:
    if not node:
        return None
    t = node.get_text(strip=True)
    return t if t else None


def get_nutrient_value(block, nutrient_label: str, replace_comma: bool = False) -> Optional[str]:
    for n in block.select('div.k10-recipe__nutrients-item'):
        spans = n.find_all('span')
        if not spans:
            continue
        label = spans[0].get_text()
        if nutrient_label in label:
            if len(spans) >= 2:
                val = spans[1].get_text(strip=True)
                if val and replace_comma:
                    val = val.replace(',', '')
                return val
    return None


def parse_page(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.select('div.k10-l-grid')
    results: List[Dict] = []
    collection_date = date.today().strftime('%b-%d-%Y')

    for item in items:
        section = None
        section_header = item.find_parent('section', class_='k10-course')
        if section_header:
            h2 = section_header.find('h2')
            section = text(h2)

        name = text(item.select_one('span.k10-recipe__name-val'))
        description = text(item.select_one('p.k10-recipe__desc'))
        allergen_labels = [s.strip() for s in item.select_one('div.k10-recipe__labels-wrapper-content').stripped_strings] if item.select_one('div.k10-recipe__labels-wrapper-content') else []

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


def crawl_walkabout():
    html = fetch(BASE_URL)
    records = parse_page(html)
    with open(file_json, 'w') as f:
        json.dump(records, f, indent=2)
    try:
        pd.DataFrame(records).to_csv(file_csv, index=False)
    except Exception as e:
        print(f'CSV export failed: {e}')
    print(f'Scraped {len(records)} items.')
    print(f'Saved: {file_json}')
    print(f'Saved: {file_csv}')


if __name__ == '__main__':
    crawl_walkabout()
