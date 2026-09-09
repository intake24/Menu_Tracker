import os
import json
from datetime import date
from typing import Dict, List, Set

import requests
import pandas as pd
from lxml import html

from define_collection_wave import folder
from helpers import create_folder, headers


BASE = 'https://www.thomasthebaker.co.uk'
START_URL = f'{BASE}/shop/index.html'
REST_NAME = 'Thomas the Baker'

# Outputs
path_out = create_folder('71_ThomasBaker', folder)
file_json = os.path.join(path_out, 'thomasbaker_items.json')
file_csv = os.path.join(path_out, 'thomasbaker_items.csv')


def fetch(url: str) -> html.HtmlElement:
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return html.fromstring(resp.content)


def absolutize(href: str) -> str:
    if not href:
        return ''
    if href.startswith('http://') or href.startswith('https://'):
        return href
    if not href.startswith('/'):
        href = '/' + href
    return BASE + href


def get_shop_links() -> List[str]:
    tree = fetch(START_URL)
    links = tree.xpath('//a/@href')
    shop_links: Set[str] = set([l for l in links if '/shop/' in (l or '')])
    return [absolutize(u) for u in sorted(shop_links)]


def get_category_name(url: str) -> str:
    parts = [p for p in url.split('/') if p]
    if not parts:
        return ''
    last = parts[-1]
    if last.endswith('.html') and len(parts) >= 2:
        return parts[-2]
    return last


def get_item_links(category_url: str) -> List[str]:
    tree = fetch(category_url)
    items = tree.xpath('//div[@class="products__item "]/a/@href')
    return [absolutize(u) for u in items]


def parse_item(url: str, category_name: str) -> Dict:
    tree = fetch(url)
    # Extract fields using original XPaths
    def x1(path: str):
        r = tree.xpath(path)
        return r[0] if r else None

    def xall(path: str):
        return tree.xpath(path)

    item_name = x1('//div[@class="product__info"]/h1/text()')
    price = x1('//div[@class="product__info__price"]/p/strong/text()')
    desc_list = xall('//div[@class="product__info__snippet"]/p/text()')
    item_description = ' '.join([d.strip() for d in desc_list if d and d.strip()]) if desc_list else None
    allergens = x1('//div[@id="allergens"]//p/text()')
    ingredients = x1('//div[@class="product__extras__item product__ingredients"]//p/text()')
    servingsize = x1('//p[@class="product__info__weight"]/text()')

    record: Dict = {
        'collection_date': date.today().strftime('%b-%d-%Y'),
        'rest_name': REST_NAME,
        'menu_section': category_name,
        'item_name': item_name,
        'price': price,
        'item_description': item_description,
        'allergens': allergens,
        'ingredients': ingredients,
        'servingsize': servingsize,
        'url': url,
    }

    # Nutrition table: add <nutrient>_100 columns
    rows = tree.xpath('//table/tbody/tr')
    for row in rows:
        values = row.xpath('./td/text()')
        if len(values) >= 2 and values[0].strip():
            key = values[0].strip() + '_100'
            val = values[1].strip()
            record[key] = val

    return record


def crawl_thomasbaker() -> List[Dict]:
    items: List[Dict] = []
    try:
        cat_pages = get_shop_links()
    except Exception as e:
        print(f'Failed to load start page: {e}')
        return items

    for cat_url in cat_pages:
        try:
            cat_name = get_category_name(cat_url)
            product_links = get_item_links(cat_url)
        except Exception as e:
            print(f'Failed to parse category {cat_url}: {e}')
            continue
        for purl in product_links:
            try:
                rec = parse_item(purl, cat_name)
                items.append(rec)
            except Exception as e:
                print(f'Failed to parse item {purl}: {e}')

    return items


def save(items: List[Dict]):
    with open(file_json, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    if items:
        pd.DataFrame(items).to_csv(file_csv, index=False)


if __name__ == '__main__':
    results = crawl_thomasbaker()
    print(f'Scraped {len(results)} items.')
    save(results)
    print(f'Saved: {file_json}')
    if os.path.exists(file_csv):
        print(f'Saved: {file_csv}')
