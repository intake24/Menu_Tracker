import os
from datetime import date
from typing import List, Dict

import pandas as pd
import requests
from lxml import html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from helpers import setup_driver
import json as pyjson
import traceback

from define_collection_wave import folder
from helpers import create_folder, headers


REST_NAME = 'Taco Bell'
# 20250917 - Be mindful that https://m.nutritionix.com/taco-bell-uk/menu/premium is in different layout
URL = 'https://www.nutritionix.com/taco-bell-uk/menu/premium'

# Outputs
path_out = create_folder('83_TacoBell', folder)
file_json = os.path.join(path_out, 'taco_bell_items.json')
file_jsonl = os.path.join(path_out, 'taco_bell_items_JSONL.json')
file_csv = os.path.join(path_out, 'taco_bell_items.csv')


def get_text(node, xpath_expr: str) -> str:
    try:
        res = node.xpath(xpath_expr)
        if not res:
            return ''
        val = res[0] if isinstance(res, list) else res
        if hasattr(val, 'text_content'):
            return val.text_content().strip()
        return str(val).strip()
    except Exception:
        return ''


def fetch_tree(url: str) -> html.HtmlElement:
    print(f"[requests] GET {url}")
    resp = requests.get(url, headers=headers, timeout=25)
    print(f"[requests] -> status {resp.status_code}, {len(resp.text):,} bytes")
    resp.raise_for_status()
    doc = html.fromstring(resp.text)
    print("[requests] Parsed HTML into lxml tree")
    return doc


def parse_items(doc: html.HtmlElement) -> List[Dict]:
    # Walk rows in order; update current category when hitting subCategory rows
    rows = doc.xpath('//tbody/tr')
    print(f"[parser] Found {len(rows)} table rows")
    current_cat = 'Unknown'
    records: List[Dict] = []
    subcat_count = 0
    for row in rows:
        cls = (row.get('class') or '').strip()
        if 'subCategory' in cls:
            # Category header row
            current_cat = get_text(row, './/h3/text()') or current_cat
            subcat_count += 1
            continue
        if ('odd' in cls) or ('even' in cls):
            name = get_text(row, './/a[contains(@class, "nmItem")]/text()')
            kj = get_text(row, './/td[@headers="inmGrid_c1"]/text()')
            kcal = get_text(row, './/td[@headers="inmGrid_c2"]/text()')
            fat = get_text(row, './/td[@headers="inmGrid_c3"]/text()')
            sat_fat = get_text(row, './/td[@headers="inmGrid_c4"]/text()')
            carb = get_text(row, './/td[@headers="inmGrid_c5"]/text()')
            sugars = get_text(row, './/td[@headers="inmGrid_c6"]/text()')
            fibre = get_text(row, './/td[@headers="inmGrid_c7"]/text()')
            protein = get_text(row, './/td[@headers="inmGrid_c8"]/text()')
            salt = get_text(row, './/td[@headers="inmGrid_c9"]/text()')
            if not name:
                continue
            record = {
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'rest_name': REST_NAME,
                'menu_section': current_cat,
                'item_name': name,
                'Energy (kj)': kj,
                'Energy (kcal)': kcal,
                'Total Fat (g)': fat,
                'Saturated Fat (g)': sat_fat,
                'Carbohydrates (g)': carb,
                'Sugars (g)': sugars,
                'Fibre (g)': fibre,
                'Protein (g)': protein,
                'Salt (g)': salt,
            }
            records.append(record)
    print(f"[parser] Detected {subcat_count} subcategory headers; built {len(records)} item rows")
    return records


def deep_find_items_from_json(obj) -> List[Dict]:
    """Recursively scan a JSON-like object for arrays of item dicts with nutrient keys."""
    candidates: List[Dict] = []
    nutrient_keys = {'kcal', 'calories', 'energy', 'kj', 'fat', 'protein', 'carb', 'sugar', 'salt'}

    def looks_like_item(d: dict) -> bool:
        if not isinstance(d, dict):
            return False
        has_name = any(k in d for k in ['name', 'item_name', 'title'])
        # nutrient-ish keys
        has_nutrient = any(any(nk in k.lower() for nk in nutrient_keys) for k in d.keys())
        return has_name and has_nutrient

    def walk(x):
        nonlocal candidates
        if isinstance(x, list):
            # if this list looks like items
            if x and all(isinstance(it, dict) for it in x):
                sample = x[0]
                if looks_like_item(sample):
                    candidates.extend(x)
                    return
            for it in x:
                walk(it)
        elif isinstance(x, dict):
            # sometimes items nested under keys like 'items', 'menu', 'products'
            for v in x.values():
                walk(v)

    walk(obj)
    return candidates


def save_outputs(records: List[Dict]):
    df = pd.DataFrame(records)
    df.to_csv(file_csv, index=False)
    df.to_json(file_json, orient='records')
    df.to_json(file_jsonl, orient='records', lines=True)
    print(f"[output] Scraped {len(records)} items.")
    try:
        sz_json = os.path.getsize(file_json)
        sz_jsonl = os.path.getsize(file_jsonl)
        sz_csv = os.path.getsize(file_csv)
        print(f"[output] Saved JSON  -> {file_json} ({sz_json:,} bytes)")
        print(f"[output] Saved JSONL -> {file_jsonl} ({sz_jsonl:,} bytes)")
        print(f"[output] Saved CSV   -> {file_csv} ({sz_csv:,} bytes)")
    except Exception:
        print(f"[output] Files written: {file_json}, {file_jsonl}, {file_csv}")


def main():
    print(f"[start] URL: {URL}")
    records: List[Dict] = []
    try:
        # Try static requests first
        print("[phase] Static parse via requests")
        doc = fetch_tree(URL)
        records = parse_items(doc)
        print(f"[phase] Static table yielded {len(records)} items")
        if not records:
            # Attempt to parse embedded JSON
            print("[phase] Static table empty; scanning embedded <script> tags for JSON")
            text = requests.get(URL, headers=headers, timeout=25).text
            scripts = html.fromstring(text).xpath('//script/text()')
            print(f"[scripts] Found {len(scripts)} script tags")
            for idx, s in enumerate(scripts):
                s = s.strip()
                if not s:
                    continue
                # Look for large JSON blobs
                try:
                    # naive approach: find first { and last }
                    start = s.find('{')
                    end = s.rfind('}')
                    if start != -1 and end != -1 and end > start:
                        snippet = s[start:end+1]
                        print(f"[scripts] Trying script #{idx+1}/{len(scripts)} with JSON-like payload ~{len(snippet):,} chars")
                        obj = pyjson.loads(snippet)
                        items = deep_find_items_from_json(obj)
                        if items:
                            print(f"[scripts] Found {len(items)} candidate items in embedded JSON (requests)")
                            for it in items:
                                name = it.get('name') or it.get('item_name') or it.get('title')
                                if not name:
                                    continue
                                records.append({
                                    'collection_date': date.today().strftime('%b-%d-%Y'),
                                    'rest_name': REST_NAME,
                                    'menu_section': it.get('category') or it.get('section') or 'Unknown',
                                    'item_name': name,
                                    'Energy (kj)': it.get('kj') or it.get('energy_kj') or '',
                                    'Energy (kcal)': it.get('kcal') or it.get('calories') or '',
                                    'Total Fat (g)': it.get('fat') or it.get('total_fat_g') or '',
                                    'Saturated Fat (g)': it.get('sat_fat') or it.get('saturated_fat_g') or '',
                                    'Carbohydrates (g)': it.get('carb') or it.get('carbohydrates_g') or '',
                                    'Sugars (g)': it.get('sugar') or it.get('sugars_g') or '',
                                    'Fibre (g)': it.get('fibre') or it.get('fiber_g') or '',
                                    'Protein (g)': it.get('protein') or it.get('protein_g') or '',
                                    'Salt (g)': it.get('salt') or it.get('sodium_g') or '',
                                })
                            print("[scripts] Stopping script scan after first hit (requests)")
                            break
                except Exception:
                    print(f"[scripts] Failed to parse script #{idx+1} as JSON; continuing")
                    continue
    except Exception as e:
        print(f"[error] Exception during requests phase: {e!r}")
        traceback.print_exc()
        records = []

    if not records:
        print("[phase] No items via requests; trying Selenium fallback...")
        print("[selenium] Initializing driver")
        driver = setup_driver()
        try:
            print("[selenium] Navigating to page")
            driver.get(URL)
            # Accept cookies if banner present
            try:
                print("[selenium] Checking for cookie banner")
                cookie_btn = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ACCEPTALLOWAGREE', 'acceptallowagree'), 'accept') or contains(translate(., 'ACCEPTALLOWAGREE', 'acceptallowagree'), 'allow') or contains(translate(., 'ACCEPTALLOWAGREE', 'acceptallowagree'), 'agree') ]"))
                )
                driver.execute_script("arguments[0].click();", cookie_btn)
                print("[selenium] Cookie banner accepted")
            except TimeoutException:
                print("[selenium] No cookie banner detected")

            # Wait for the table rows to render
            try:
                print("[selenium] Waiting for table rows to render")
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//tbody/tr"))
                )
                print("[selenium] Table rows present")
            except TimeoutException:
                print("[selenium] Timed out waiting for table rows")

            # Scroll to ensure lazy content loads
            try:
                print("[selenium] Scrolling to load lazy content")
                prev_height = driver.execute_script("return document.body.scrollHeight")
                for i in range(3):
                    print(f"[selenium] Scroll pass {i+1}")
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    WebDriverWait(driver, 5).until(lambda d: True)
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    if new_height == prev_height:
                        print("[selenium] No further growth in page height; stopping scroll")
                        break
                    prev_height = new_height
            except Exception:
                print("[selenium] Error during scrolling; continuing")

            tree = html.fromstring(driver.page_source)
            records = parse_items(tree)
            print(f"[selenium] Parsed {len(records)} items from table")
            if not records:
                # Attempt embedded JSON from rendered scripts
                print("[selenium] Table empty; scanning embedded <script> tags for JSON")
                scripts = html.fromstring(driver.page_source).xpath('//script/text()')
                print(f"[selenium] Found {len(scripts)} script tags")
                for idx, s in enumerate(scripts):
                    s = s.strip()
                    if not s:
                        continue
                    try:
                        start = s.find('{')
                        end = s.rfind('}')
                        if start != -1 and end != -1 and end > start:
                            snippet = s[start:end+1]
                            print(f"[selenium] Trying script #{idx+1}/{len(scripts)} with JSON-like payload ~{len(snippet):,} chars")
                            obj = pyjson.loads(snippet)
                            items = deep_find_items_from_json(obj)
                            if items:
                                print(f"[selenium] Found {len(items)} candidate items in embedded JSON (rendered)")
                                for it in items:
                                    name = it.get('name') or it.get('item_name') or it.get('title')
                                    if not name:
                                        continue
                                    records.append({
                                        'collection_date': date.today().strftime('%b-%d-%Y'),
                                        'rest_name': REST_NAME,
                                        'menu_section': it.get('category') or it.get('section') or 'Unknown',
                                        'item_name': name,
                                        'Energy (kj)': it.get('kj') or it.get('energy_kj') or '',
                                        'Energy (kcal)': it.get('kcal') or it.get('calories') or '',
                                        'Total Fat (g)': it.get('fat') or it.get('total_fat_g') or '',
                                        'Saturated Fat (g)': it.get('sat_fat') or it.get('saturated_fat_g') or '',
                                        'Carbohydrates (g)': it.get('carb') or it.get('carbohydrates_g') or '',
                                        'Sugars (g)': it.get('sugar') or it.get('sugars_g') or '',
                                        'Fibre (g)': it.get('fibre') or it.get('fiber_g') or '',
                                        'Protein (g)': it.get('protein') or it.get('protein_g') or '',
                                        'Salt (g)': it.get('salt') or it.get('sodium_g') or '',
                                    })
                                print("[selenium] Stopping script scan after first hit (rendered)")
                                break
                    except Exception:
                        print(f"[selenium] Failed to parse script #{idx+1} as JSON; continuing")
                        continue
        finally:
            driver.quit()
    save_outputs(records)


if __name__ == '__main__':
    main()
