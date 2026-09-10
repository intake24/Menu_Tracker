import json
import os
from datetime import date
from typing import Dict, List

import requests
from lxml import html
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder

BASE_URL = 'https://www.boostjuicebars.co.uk/drinks/'
REST_NAME = 'Boost Juice Bars'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Outputs
path_out = create_folder('43_Boostjuice', folder)
file_json = os.path.join(path_out, 'boostjuice_items.json')
file_csv = os.path.join(path_out, 'boostjuice_items.csv')


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_list(html_text: str) -> List[str]:
    sc = html.fromstring(html_text)
    ids = sc.xpath('//ul[@id="og-grid"]/li/a/@id')
    links = [BASE_URL + i for i in ids]
    # dedupe
    seen = set()
    unique = []
    for u in links:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def parse_item(html_text: str) -> Dict:
    sc = html.fromstring(html_text)
    item_name = ''.join(sc.xpath('//div[@class="quick-overview"]/h2/text()'))
    item_desc = ''.join(sc.xpath('//div[@class="quick-overview"]/p/text()'))
    servingsizes = sc.xpath('//div[@class="tabs-nav"]/a/text()')
    org = sc.xpath('//div[@class="org info-table"]/ul/li/strong/text()')
    med = sc.xpath('//div[@class="med info-table"]/ul/li/strong/text()')
    kids = sc.xpath('//div[@class="kid info-table"]/ul/li/strong/text()')

    nutrient_list = [org]
    if med:
        nutrient_list.append(med)
    if kids:
        nutrient_list.append(kids)

    headers = ['kcal', 'fat', 'carb', 'fibre', 'protein', 'satfat', 'sugar', 'sodium']

    base: Dict = {
        'rest_name': REST_NAME,
        'collection_date': date.today().strftime('%b-%d-%Y'),
        'item_name': item_name,
        'item_description': item_desc,
    }

    records: List[Dict] = []
    for i in range(len(servingsizes)):
        nutrition_dict = dict(zip(headers, nutrient_list[i] if len(servingsizes) > 1 else org))
        nutrition_dict.update({'servingsize': servingsizes[i]})
        rec = base.copy()
        rec.update(nutrition_dict)
        records.append(rec)
    return {'base': base, 'variants': records}


def crawl_boostjuice():
    listing_html = fetch(BASE_URL)
    product_links = parse_list(listing_html)

    all_records: List[Dict] = []
    for url in product_links:
        try:
            html_text = fetch(url)
            parsed = parse_item(html_text)
            all_records.extend(parsed['variants'])
        except Exception as e:
            print(f'Failed {url}: {e}')

    with open(file_json, 'w') as f:
        json.dump(all_records, f, indent=2)
    try:
        pd.DataFrame(all_records).to_csv(file_csv, index=False)
    except Exception as e:
        print(f'CSV export failed: {e}')
    print(f'Scraped {len(all_records)} items from {len(product_links)} products.')
    print(f'Saved: {file_json}')
    print(f'Saved: {file_csv}')


if __name__ == '__main__':
    crawl_boostjuice()
