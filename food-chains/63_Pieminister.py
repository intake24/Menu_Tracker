import os
import json
from datetime import date
from typing import Dict, List

import requests
import pandas as pd
from lxml import html

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from define_collection_wave import folder
from helpers import create_folder, headers, setup_driver

REST_NAME = 'Pieminister'
# Switch to the shop site collection which lists individual product pages
SHOP_BASE = 'https://shop.pieminister.co.uk'
START_URLS = [
    f'{SHOP_BASE}/collections/pies/'
    # You can add more collections if needed, e.g. f'{SHOP_BASE}/collections/patties/'
]

# Outputs
path_out = create_folder('63_Pieminister', folder)
file_json = os.path.join(path_out, 'pieminister_items.json')
file_csv = os.path.join(path_out, 'pieminister_items.csv')


def fetch(url: str) -> html.HtmlElement:
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return html.fromstring(resp.content)


def parse_item_page(item_url: str, menu_section: str) -> Dict:
    sc = fetch(item_url)

    # Prefer JSON-LD Product data when available
    item_name = ''
    item_description = ''
    for s in sc.xpath('//script[@type="application/ld+json"]/text()'):
        try:
            data = json.loads(s)
        except Exception:
            continue
        # JSON-LD may be an object or a list
        candidates = data if isinstance(data, list) else [data]
        for node in candidates:
            if isinstance(node, dict) and node.get('@type') in ('Product', ['Product']):
                item_name = node.get('name') or item_name
                item_description = node.get('description') or item_description
    # Fallbacks for title/description
    if not item_name:
        # Try OpenGraph or <title>
        item_name = sc.xpath('normalize-space(//meta[@property="og:title"]/@content)') or \
                    sc.xpath('normalize-space(//title/text())')
        # Clean common suffixes
        if '|' in item_name:
            item_name = item_name.split('|')[0].strip()
    if not item_description:
        # Try meta description
        item_description = sc.xpath('normalize-space(//meta[@name="description"]/@content)')

    # Ingredients (best-effort): capture text after a heading containing 'Ingredients'
    ingredients = ''
    ing_nodes = sc.xpath("//*[self::h2 or self::h3 or self::p][contains(translate(normalize-space(.), 'INGREDIENTS', 'ingredients'), 'ingredients')]")
    if ing_nodes:
        # Collect following sibling texts up to next heading-like element
        sib_texts = []
        for sib in ing_nodes[0].xpath('following-sibling::*'):
            tag = sib.tag.lower()
            if tag in ('h2', 'h3', 'h4'):
                break
            txt = ' '.join([t.strip() for t in sib.xpath('.//text()') if t.strip()])
            if txt:
                sib_texts.append(txt)
        if sib_texts:
            ingredients = ' '.join(sib_texts)

    # Nutrition table: look for a 3-column table: metric | per 100g | per pie
    nutrition_dict: Dict[str, str] = {}
    tables = sc.xpath('//table')
    for tbl in tables:
        rows = tbl.xpath('.//tr')
        if not rows:
            continue
        # Heuristic: header row contains 'Typical values' and column names
        header_cells = [c.text_content().strip() for c in rows[0].xpath('./th|./td')]
        if not header_cells:
            continue
        # Continue regardless of the exact header labels; assume 3 columns if present
        for row in rows[1:] if len(rows) > 1 else []:
            cells = [c.text_content().strip() for c in row.xpath('./td|./th')]
            if len(cells) >= 3:
                key, per100, perpie = cells[0], cells[1], cells[2]
                if key:
                    if per100:
                        nutrition_dict[f'{key}_per100'] = per100
                    if perpie:
                        nutrition_dict[f'{key}_perserving'] = perpie  # keep naming consistent with existing scripts

    record: Dict[str, str] = {
        'rest_name': REST_NAME,
        'collection_date': date.today().strftime('%b-%d-%Y'),
        'menu_section': menu_section,
        'item_name': item_name,
        'item_description': item_description,
        'ingredients': ingredients,
        'url': item_url,
    }
    record.update(nutrition_dict)
    return record


def parse_category(category_url: str) -> List[Dict]:
    # derive menu section from collection path
    parts = category_url.rstrip('/').split('/')
    menu_section = parts[-1] if parts and parts[-2] == 'collections' else 'pies'

    records: List[Dict] = []

    # Strategy 1: Static HTML via requests (Shopify collection page)
    item_urls: List[str] = []
    try:
        tree = fetch(category_url)
        # Typical Shopify: product links under /products/
        item_urls = tree.xpath('//a[contains(@href, "/products/")]/@href')
    except requests.HTTPError as e:
        print(f'HTTP error for {category_url}: {e}')

    # Normalize to absolute URLs and filter to shop domain
    normalized_urls: List[str] = []
    for href in item_urls:
        if not href:
            continue
        if href.startswith('/'):
            href = f'{SHOP_BASE}{href}'
        if href.startswith(SHOP_BASE):
            normalized_urls.append(href)

    # Deduplicate
    normalized_urls = list(dict.fromkeys(normalized_urls))

    # If still nothing, try Selenium to render lazy content
    if not normalized_urls:
        print(f'No product links found statically on {category_url}; trying Selenium...')
        driver = setup_driver()
        try:
            driver.get(category_url)
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, 'a'))
            )
            anchors = driver.find_elements(By.TAG_NAME, 'a')
            hrefs = [a.get_attribute('href') for a in anchors]
            for h in hrefs:
                if h and h.startswith(f'{SHOP_BASE}/products/'):
                    normalized_urls.append(h)
            normalized_urls = list(dict.fromkeys(normalized_urls))
            print(f'Found {len(normalized_urls)} product links via Selenium')
        except TimeoutException:
            print('Timed out waiting for collection to load in Selenium')
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    for href in normalized_urls:
        try:
            rec = parse_item_page(href, menu_section)
            if rec.get('item_name'):
                records.append(rec)
            else:
                print(f'Skipping non-item page (no name): {href}')
        except Exception as e:
            print(f'Failed to parse item {href}: {e}')
    return records


def crawl_pieminister() -> List[Dict]:
    all_records: List[Dict] = []
    for url in START_URLS:
        try:
            recs = parse_category(url)
            all_records.extend(recs)
        except Exception as e:
            print(f'Failed to parse category {url}: {e}')
    return all_records


def save(records: List[Dict]):
    with open(file_json, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    if records:
        pd.DataFrame(records).to_csv(file_csv, index=False)


if __name__ == '__main__':
    records = crawl_pieminister()
    print(f'Scraped {len(records)} items')
    save(records)
    print(f'Saved: {file_json}')
    if os.path.exists(file_csv):
        print(f'Saved: {file_csv}')
