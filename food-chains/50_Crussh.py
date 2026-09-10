import json
import os
from datetime import date
from time import sleep
from typing import Dict, List

import pandas as pd
import requests
from lxml import html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from define_collection_wave import folder
from helpers import create_folder, setup_driver

BASE_URL = 'https://crussh.com/'
REST_NAME = 'Crussh'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Outputs
path_out = create_folder('50_Crussh', folder)
file_json = os.path.join(path_out, 'crussh_items.json')
file_csv = os.path.join(path_out, 'crussh_items.csv')


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def get_category_links(driver) -> List[str]:
    # Discover category links client-side to avoid 404 on old paths
    driver.get(BASE_URL)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
    anchors = driver.find_elements(By.XPATH, "//a[contains(@href,'menu-category')]")
    links = []
    seen = set()
    for a in anchors:
        href = a.get_attribute('href')
        if href and 'menu-category' in href and href not in seen:
            seen.add(href)
            links.append(href)
    # Fallback: try legacy /menu/ page if nothing found
    if not links:
        try:
            driver.get('https://crussh.com/menu/')
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            anchors = driver.find_elements(By.XPATH, "//a[contains(@href,'menu-category')]")
            for a in anchors:
                href = a.get_attribute('href')
                if href and 'menu-category' in href and href not in seen:
                    seen.add(href)
                    links.append(href)
        except Exception:
            pass
    return links


def get_item_links_from_category(driver, category_url: str) -> (str, List[str]):
    driver.get(category_url)
    # Allow JS to populate
    WebDriverWait(driver, 30).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div[data-url*="menu-item/"]'))
    )
    # category slug from url
    category = category_url.strip('/').split('/')[-1]
    cards = driver.find_elements(By.CSS_SELECTOR, 'div[data-url*="menu-item/"]')
    links = []
    for c in cards:
        href = c.get_attribute('data-url')
        if href:
            links.append(href)
    return category, links


def parse_item_page(html_text: str, category: str) -> Dict:
    sc = html.fromstring(html_text)
    item_name = sc.xpath('//h1[contains(@class, "elementor-heading-title")]/text()')
    item_name = item_name[0].strip() if item_name else ''
    item_description = sc.xpath('normalize-space(//div[@data-id="496f50a"]/div/text())')
    allergens = sc.xpath('normalize-space(//h3[contains(@class, "elementor-icon-box-title")]/span/text())')
    ingredients = ''.join(sc.xpath('//div[@data-id="58bb1f8"]/div/p//text()'))

    # Table nutrients appear as repeating triplets: [name, per100, perServ]
    nutrients = sc.xpath('//table//div//text()')
    my_dict: Dict[str, str] = {}
    for i in range(0, len(nutrients), 3):
        try:
            key = nutrients[i].strip()
            per100 = nutrients[i+1].strip()
            per_serv = nutrients[i+2].strip()
        except IndexError:
            continue
        if key:
            my_dict[key] = per_serv
            my_dict[f'{key}_100'] = per100

    record = {
        'rest_name': REST_NAME,
        'collection_date': date.today().strftime('%b-%d-%Y'),
        'menu_section': category,
        'item_name': item_name,
        'item_description': item_description,
        'allergens': allergens,
        'ingredients': ingredients,
    }
    record.update(my_dict)
    return record


def crawl_crussh():
    driver = setup_driver()
    try:
        categories = get_category_links(driver)
        if not categories:
            raise RuntimeError("Crussh's official domain no longer publishes a menu")
        all_records: List[Dict] = []
        for cat in categories:
            try:
                category_slug, item_links = get_item_links_from_category(driver, cat)
            except Exception as e:
                print(f'Failed category {cat}: {e}')
                continue

            for url in item_links:
                try:
                    html_text = fetch(url)
                    rec = parse_item_page(html_text, category_slug)
                    all_records.append(rec)
                except Exception as e:
                    print(f'  Failed item {url}: {e}')

        with open(file_json, 'w') as f:
            json.dump(all_records, f, indent=2)
        try:
            pd.DataFrame(all_records).to_csv(file_csv, index=False)
        except Exception as e:
            print(f'CSV export failed: {e}')
        print(f'Scraped {len(all_records)} items from {len(categories)} categories.')
        print(f'Saved: {file_json}')
        print(f'Saved: {file_csv}')
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    crawl_crussh()
