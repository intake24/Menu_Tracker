import json
import os
from datetime import date
from typing import List, Dict

import pandas as pd
import requests
from bs4 import BeautifulSoup

from define_collection_wave import folder
from helpers import create_folder, headers


REST_NAME = "Coco Di Mama"
BASE_URL = "https://www.cocodimama.co.uk"
MENU_URL = f"{BASE_URL}/menus"

# Outputs
path_out = create_folder('84_Coco', folder)
file_json = os.path.join(path_out, 'coco_di_mama_items.json')
file_jsonl = os.path.join(path_out, 'coco_di_mama_items_JSONL.json')
file_csv = os.path.join(path_out, 'coco_di_mama_items.csv')


def fetch_menu_html() -> str:
    resp = requests.get(MENU_URL, headers=headers, timeout=25)
    resp.raise_for_status()
    return resp.text


def build_records_from_menu_json_ld(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, 'html.parser')
    menu = None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or '')
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get('@type') == 'Menu':
            menu = payload
            break

    if not menu:
        raise RuntimeError('No schema.org Menu JSON-LD found on the menu page')

    records: List[Dict] = []
    menu_name = menu.get('name') or 'Coco Di Mama Menu'
    sections = menu.get('hasMenuSection') or []

    for section in sections:
        section_title = section.get('name') or ''
        for item in section.get('hasMenuItem') or []:
            dietary = item.get('suitableForDiet') or []
            if not isinstance(dietary, list):
                dietary = [dietary]
            records.append({
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'rest_name': REST_NAME,
                'menu_name': menu_name,
                'menu_section': section_title,
                'item_name': item.get('name'),
                'item_id': None,
                'kcal': (item.get('nutrition') or {}).get('calories'),
                'item_description': item.get('description'),
                'price': (item.get('offers') or {}).get('price', ''),
                'dietary': ', '.join(value.rsplit('/', 1)[-1] for value in dietary),
            })
    return records


def save_outputs(records: List[Dict]):
    df = pd.DataFrame(records)
    df.to_csv(file_csv, index=False)
    df.to_json(file_json, orient='records')
    df.to_json(file_jsonl, orient='records', lines=True)
    print(f"Saved {len(df)} items to:\n- {file_json}\n- {file_jsonl}\n- {file_csv}")


def main():
    print(f"[start] Fetching menu from: {MENU_URL}")
    records = build_records_from_menu_json_ld(fetch_menu_html())
    print(f"[info] Parsed {len(records)} menu item(s)")
    save_outputs(records)


if __name__ == '__main__':
    main()
