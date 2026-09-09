import os
from datetime import date
from typing import List, Dict

import pandas as pd
from lxml import html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from helpers import setup_driver

from define_collection_wave import folder
from helpers import create_folder


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
    print("[selenium] Initializing driver")
    driver = setup_driver()
    try:
        # Force desktop layout to match table-based DOM (set UA and viewport BEFORE navigation)
        try:
            driver.set_window_size(1280, 900)
            print("[selenium] Set desktop window size 1280x900")
        except Exception:
            pass
        # Override user agent to a desktop Chrome to avoid mobile layout
        DESKTOP_UA = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        try:
            driver.execute_cdp_cmd('Network.enable', {})
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {'userAgent': DESKTOP_UA})
            ua_now = driver.execute_script("return navigator.userAgent")
            print(f"[selenium] User-Agent set to: {ua_now}")
        except Exception:
            print("[selenium] Could not override User-Agent; continuing with default")

        print("[selenium] Navigating to page")
        driver.get(URL)

        # Ensure initial page load complete
        try:
            WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
            print("[selenium] Document readyState is complete")
        except Exception:
            print("[selenium] readyState wait skipped/failed; continuing")

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

        # Wait for the table rows (or item anchors) to render
        try:
            print("[selenium] Waiting for table rows to render")
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((By.XPATH, "//tbody/tr | //a[contains(@class,'nmItem')]"))
            )
            print("[selenium] Table/item elements present")
        except TimeoutException:
            print("[selenium] Timed out waiting for table rows; will attempt scroll and retry")

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

        # Parse the rendered HTML (first pass)
        tree = html.fromstring(driver.page_source)
        records = parse_items(tree)
        print(f"[selenium] Parsed {len(records)} items from table (pass 1)")

        # If no records, attempt a focused retry with additional waits and scrolling
        if not records:
            try:
                print("[selenium] Retry: waiting explicitly for nmItem anchors")
                WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@class,'nmItem')]"))
                )
            except TimeoutException:
                print("[selenium] Retry: nmItem anchors not detected within timeout")

            try:
                # Progressive scroll to trigger virtualization
                print("[selenium] Retry: progressive scroll")
                for y in (200, 600, 1000, 1600, 2200):
                    driver.execute_script("window.scrollTo(0, arguments[0]);", y)
                    WebDriverWait(driver, 2).until(lambda d: True)
                # back to top
                driver.execute_script("window.scrollTo(0, 0);")
            except Exception:
                print("[selenium] Retry: scrolling failed; continuing")

            tree = html.fromstring(driver.page_source)
            records = parse_items(tree)
            print(f"[selenium] Parsed {len(records)} items from table (pass 2)")

    finally:
        driver.quit()

    save_outputs(records)


if __name__ == '__main__':
    main()
