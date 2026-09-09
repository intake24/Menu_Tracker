import os
import json
from datetime import date
from time import sleep
from typing import Dict, List, Tuple

import requests
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder


# Basic config
REST_NAME = 'JOE & THE JUICE'
STORE_ID = '186f925b-8932-4195-8e67-6e5d01b8bfc2'
BASE_LAYOUT_URL = 'https://joepay-api.joejuice.com/me/products/layout'
BASE_PRODUCT_URL = 'https://joepay-api.joejuice.com/me/products'
BASE_STORE_URL = f'https://joepay-api.joejuice.com/me/stores/{STORE_ID}'

HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9,en-IN;q=0.8',
    'origin': 'https://www.joejuice.com',
    'referer': 'https://www.joejuice.com/',
    'sec-ch-ua': '"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36 Edg/130.0.0.0',
    'x-joe-web': 'true',
    'x-joeloyalty-version': '2.7.0',
}

# Outputs
path_out = create_folder('55_JoeJuice', folder)
file_json = os.path.join(path_out, 'joejuice_items.json')
file_csv = os.path.join(path_out, 'joejuice_items.csv')

session = requests.Session()


def fetch_layout() -> List[Dict]:
    params = {'storeId': STORE_ID, 'type': 'all'}
    resp = session.get(BASE_LAYOUT_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    try:
        return resp.json()
    except Exception:
        return json.loads(resp.text)


def get_product_details(product_id: str, max_retries: int = 3, retry_delay: int = 2) -> Tuple[Dict[str, str], Dict[str, str]]:
    nutrition: Dict[str, str] = {}
    allergens: Dict[str, str] = {}

    # 1) Fetch ingredients list for the product variant
    params = {'storeId': STORE_ID}
    ingredients: List[Dict] = []
    for attempt in range(max_retries):
        try:
            r = session.get(f'{BASE_PRODUCT_URL}/{product_id}', params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            details = r.json()
            ingredients = (details.get('productVariants') or [{}])[0].get('ingredients', [])
            break
        except Exception as e:
            print(f'Attempt {attempt + 1} failed for product {product_id}: {e}')
            if attempt < max_retries - 1:
                print(f'Retrying in {retry_delay} seconds...')
                sleep(retry_delay)
            else:
                return nutrition, allergens

    if not ingredients:
        return nutrition, allergens

    # 2) Nutrition
    nutrition_data = [{'id': ing['id'], 'ingredientAmount': ing.get('ingredientAmount')} for ing in ingredients]
    for attempt in range(max_retries):
        try:
            r = session.post(f'{BASE_STORE_URL}/ingredients/nutrition', headers=HEADERS, json=nutrition_data, timeout=30)
            r.raise_for_status()
            data = r.json().get('data', [])
            for n in data:
                name = n.get('name')
                val = n.get('value')
                if name:
                    nutrition[name] = val
            break
        except Exception as e:
            print(f'Attempt {attempt + 1} failed for nutrition data: {e}')
            if attempt < max_retries - 1:
                print(f'Retrying in {retry_delay} seconds...')
                sleep(retry_delay)

    # 3) Allergens
    allergen_data = [{'id': ing['id']} for ing in ingredients]
    for attempt in range(max_retries):
        try:
            r = session.post(f'{BASE_STORE_URL}/ingredients/allergens', headers=HEADERS, json=allergen_data, timeout=30)
            r.raise_for_status()
            arr = r.json()
            for a in arr:
                nm = a.get('name')
                deg = a.get('degree', 'None')
                if nm:
                    allergens[nm] = deg
            break
        except Exception as e:
            print(f'Attempt {attempt + 1} failed for allergen data: {e}')
            if attempt < max_retries - 1:
                print(f'Retrying in {retry_delay} seconds...')
                sleep(retry_delay)

    return nutrition, allergens


def build_records(categories: List[Dict]) -> List[Dict]:
    records: List[Dict] = []
    today = date.today().strftime('%b-%d-%Y')
    for cat in categories:
        category_name = cat.get('name')
        products = cat.get('tiles', [])
        for product in products:
            product_id = product.get('id')
            product_name = product.get('name', '')
            product_description = product.get('description', '')
            product_price = product.get('priceRange', '')
            if isinstance(product_price, list):
                product_price = product_price[0] if product_price else ''

            # Filter as in original: only proceed if product tile has ingredients key
            if not product.get('ingredients'):
                continue

            nutrition, allergens = get_product_details(product_id)

            base: Dict[str, str] = {
                'collection_date': today,
                'rest_name': REST_NAME,
                'menu_section': category_name,
                'item_name': product_name,
                'item_description': product_description,
                'product_price': product_price,
            }
            base.update(nutrition)
            base.update(allergens)
            records.append(base)
    return records


def crawl_joejuice():
    categories = fetch_layout()
    print(f'Total categories: {len(categories)}')
    records = build_records(categories)

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
    crawl_joejuice()
