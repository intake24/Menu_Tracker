import os
import json
from datetime import date
from typing import Dict, List, Optional

import requests
import pandas as pd
from lxml import html

from define_collection_wave import folder
from helpers import create_folder, headers, setup_driver, clean_text
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


START_URL = 'https://birdsbakery.com/pages/nutrition-and-allergen-data'
REST_NAME = 'Birds Bakery'

# Outputs
path_out = create_folder('78_BirdsBakery', folder)
file_json = os.path.join(path_out, 'birdsbakery_items.json')
file_csv = os.path.join(path_out, 'birdsbakery_items.csv')


def fetch_tree(url: str) -> html.HtmlElement:
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return html.fromstring(resp.content)


def discover_item_links() -> List[str]:
    """Try to discover product data links from the nutrition page.

    First attempt a static parse; if none found, fall back to Selenium to wait for the app content.
    """
    links: List[str] = []
    try:
        tree = fetch_tree(START_URL)
        # Try direct static anchors under the app container
        anchors = tree.xpath('//*[@id="nutrition-and-allergen-data-app"]//a/@href')
        links = [a if a.startswith('http') else f'https://birdsbakery.com{a}' for a in anchors]
        links = list(dict.fromkeys(links))
        if links:
            return links
    except Exception:
        pass

    # Selenium fallback
    driver = setup_driver()
    try:
        driver.get(START_URL)
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((
                By.XPATH,
                '//*[@id="nutrition-and-allergen-data-app"]//ul//li//a'
            ))
        )
        elems = driver.find_elements(By.XPATH, '//*[@id="nutrition-and-allergen-data-app"]//ul//li//a')
        hrefs = [e.get_attribute('href') for e in elems if e.get_attribute('href')]
        # de-dup and normalize
        links = []
        seen = set()
        for h in hrefs:
            url = h if h.startswith('http') else f'https://birdsbakery.com{h}'
            if url not in seen:
                seen.add(url)
                links.append(url)
    finally:
        driver.quit()
    return links


def parse_item(url: str) -> Optional[Dict]:
    try:
        tree = fetch_tree(url)
    except Exception as e:
        print(f'Failed to load {url}: {e}')
        return None

    # Product name
    name = tree.xpath('normalize-space(//h1/text())') or None
    if name:
        name = name.replace(' data', '')

    # Identify the nutrition data section (Shopify section id contains nutrition_data_item)
    # This is more robust than using the full dynamic id used in the old spider
    section_nodes = tree.xpath('//section[contains(@id, "nutrition_data_item")]')
    allergen: Optional[str] = None
    if section_nodes:
        sec = section_nodes[0]
        # Try to find a paragraph containing the word Allergens
        allerg_ps = sec.xpath('.//p[contains(translate(., "ALLERGENS", "allergens"), "allergen")]/text()')
        if allerg_ps:
            allergen = ' '.join([t.strip() for t in allerg_ps if t and t.strip()]) or None
        if not allergen:
            # fallback to any p text in expected block
            ptxt = sec.xpath('.//div/div[1]/div/div[3]/p/text()')
            if ptxt:
                allergen = ' '.join([t.strip() for t in ptxt if t and t.strip()]) or None
    else:
        sec = None

    item: Dict = {
        'collection_date': date.today().strftime('%b-%d-%Y'),
        'rest_name': REST_NAME,
        'item_name': clean_text(name) if name else None,
        'allergen': clean_text(allergen) if allergen else None,
    }

    # Nutrition table: td[1]=key, td[2]=value per 100; strip unit characters like space, mg, kcal, J
    if sec is None:
        rows = tree.xpath('//table/tbody/tr')
    else:
        rows = sec.xpath('.//table/tbody/tr')
    for r in rows:
        key = (r.xpath('./td[1]/text()') or [''])[0].strip()
        val = (r.xpath('./td[2]/text()') or [''])[0].strip()
        if not key:
            continue
        # replicate original strip of ' mgkcalJ'
        val_stripped = val.strip(' mgkcalJ') if val else val
        item[f'{key}_100'] = val_stripped

    return item


def crawl_birdsbakery() -> List[Dict]:
    items: List[Dict] = []
    links = discover_item_links()
    if not links:
        print('No item links found on the nutrition page. The site may be dynamic or has changed.')
        return items
    for link in links:
        rec = parse_item(link)
        if rec:
            items.append(rec)
    return items


def save(items: List[Dict]):
    with open(file_json, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    if items:
        pd.DataFrame(items).to_csv(file_csv, index=False)


if __name__ == '__main__':
    results = crawl_birdsbakery()
    print(f'Scraped {len(results)} items.')
    save(results)
    print(f'Saved: {file_json}')
    if os.path.exists(file_csv):
        print(f'Saved: {file_csv}')
