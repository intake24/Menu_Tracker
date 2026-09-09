import json
import os
from datetime import date
from typing import Dict, List

import requests
from lxml import html
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder

BASE_URL = 'https://www.benugo.com/sites/cafes/benugo-st-pancras/'
REST_NAME = 'Benugo Cafe'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Outputs
path_out = create_folder('42_Benugo', folder)
file_json = os.path.join(path_out, 'benugo_items.json')
file_csv = os.path.join(path_out, 'benugo_items.csv')


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_menu_json(html_text: str) -> List[Dict]:
    sc = html.fromstring(html_text)
    script_texts = sc.xpath('//div[@class="product-menu-wrapper"]/script/text()')
    if not script_texts:
        return []
    # The JSON is embedded inside backticks in the first script tag
    raw = script_texts[0]
    try:
        menus = json.loads(raw.split('`')[1]).get('Menus')
    except Exception:
        menus = []
    return menus or []


def build_records(menus: List[Dict]) -> List[Dict]:
    records: List[Dict] = []
    collection_date = date.today().strftime('%b-%d-%Y')

    for menu in menus:
        menu_section = menu.get('Name')
        subsections = menu.get('Sections') or []
        for subsection in subsections:
            section_name = subsection.get('Name')
            items = subsection.get('Recipes') or []
            for item in items:
                nutrients = item.get('Nutrs') or []
                base = {
                    'rest_name': REST_NAME,
                    'collection_date': collection_date,
                    'menu_section': f"{menu_section},{section_name}" if section_name else menu_section,
                    'item_name': item.get('Name'),
                    'item_description': item.get('Desc'),
                }
                # Sizes array for serving info
                sizes = item.get('Sizes') or []
                if sizes and isinstance(sizes, list):
                    size0 = sizes[0] or {}
                    base['servingsize'] = size0.get('Size')
                    base['servingsizeunit'] = size0.get('Uom1')

                # Flatten nutrient pairs (PerServ and Per100g)
                for n in nutrients:
                    desc = (n or {}).get('Desc')
                    if not desc:
                        continue
                    base[desc] = (n or {}).get('PerServ')
                    base[f"{desc}_100"] = (n or {}).get('Per100g')

                records.append(base)
    return records


def crawl_benugo():
    html_text = fetch(BASE_URL)
    menus = extract_menu_json(html_text)
    records = build_records(menus)

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
    crawl_benugo()
