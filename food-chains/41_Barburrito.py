import json
import os
from datetime import date
from typing import Dict, List

import requests
from lxml import html
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder

BASE_URL = 'https://tkmenus.com/barburrito'
REST_NAME = 'Barburrito'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Outputs
path_out = create_folder('41_Barburrito', folder)
file_json = os.path.join(path_out, 'barburrito_items.json')
file_csv = os.path.join(path_out, 'barburrito_items.csv')


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_page(html_text: str) -> List[Dict]:
    sc = html.fromstring(html_text)
    nodes = sc.xpath('//div[@class="k10-byo-item__name-container"]')
    results: List[Dict] = []
    collection_date = date.today().strftime('%b-%d-%Y')

    for n in nodes:
        name = n.xpath('normalize-space(./span[@class="k10-byo-item__name-wrapper"]/text())')
        kcal = n.xpath('normalize-space(./span[@class="k10-byo-item__nutrient_energy"]/text())')
        if not name and not kcal:
            continue
        results.append({
            'rest_name': REST_NAME,
            'collection_date': collection_date,
            'item_name': name or None,
            'kcal': kcal or None,
        })
    return results


def crawl_barburrito():
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
    crawl_barburrito()
