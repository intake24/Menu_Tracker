import os
import re
from datetime import date
from typing import List, Dict

import pandas as pd
import requests
from lxml import html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from define_collection_wave import folder
from helpers import create_folder, headers, setup_driver

REST_NAME = "Nicholson's"
BASE = 'https://www.smartchef.co.uk'
LIST_URL = f'{BASE}/brands/nicholsons'
ITEMS_URL = f'{BASE}/Brands/SuburbanMenuItems?menuid={{menuid}}'

# Outputs
path_out = create_folder('91_Nicholsons', folder)
file_json = os.path.join(path_out, 'nicholsons_items.json')
file_jsonl = os.path.join(path_out, 'nicholsons_items_JSONL.json')
file_csv = os.path.join(path_out, 'nicholsons_items.csv')


def fetch_tree(url: str) -> html.HtmlElement:
    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()
    return html.fromstring(resp.text)


def extract_menu_ids(doc: html.HtmlElement) -> List[str]:
    hrefs = doc.xpath('.//div[@class="hidden-small"]/div/ul/li/a/@href')
    menuids: List[str] = []
    for href in hrefs:
        # Original spider: regex find values in quotes from the href string
        m = re.findall("\'([^\"]*)\'", href)
        if m:
            menuids.append(m[0])
    return menuids


def extract_menu_ids_selenium() -> List[str]:
    """Use Selenium to render the brand page and extract menuids from anchors or page source."""
    driver = setup_driver()
    ids: List[str] = []
    try:
        # Force desktop layout & UA for predictable DOM
        try:
            driver.set_window_size(1280, 900)
        except Exception:
            pass
        DESKTOP_UA = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        try:
            driver.execute_cdp_cmd('Network.enable', {})
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {'userAgent': DESKTOP_UA})
        except Exception:
            pass

        driver.get(LIST_URL)
        # Try to accept cookie banner if present
        try:
            cookie_btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ACCEPTALLOWAGREE', 'acceptallowagree'), 'accept') or contains(translate(., 'ACCEPTALLOWAGREE', 'acceptallowagree'), 'allow') or contains(translate(., 'ACCEPTALLOWAGREE', 'acceptallowagree'), 'agree') ]"))
            )
            driver.execute_script("arguments[0].click();", cookie_btn)
        except TimeoutException:
            pass
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//div[@class='hidden-small']"))
            )
        except TimeoutException:
            pass

        # Wait for potential containers
        try:
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'hidden-small')]|//ul|//nav"))
            )
        except TimeoutException:
            pass

        # Scroll a bit to trigger lazy content
        try:
            prev_h = driver.execute_script("return document.body.scrollHeight")
            for _ in range(2):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                WebDriverWait(driver, 2).until(lambda d: True)
                new_h = driver.execute_script("return document.body.scrollHeight")
                if new_h == prev_h:
                    break
                prev_h = new_h
            driver.execute_script("window.scrollTo(0, 0);")
        except Exception:
            pass

        # Collect href/onclick from anchors in likely containers
        anchors = driver.find_elements(By.XPATH, "//div[contains(@class,'hidden-small')]//a | //ul//li//a | //nav//a")
        for a in anchors:
            href = a.get_attribute('href') or ''
            onclick = a.get_attribute('onclick') or ''
            for source in (href, onclick):
                # Match any single-quoted token (mirror original spider's approach)
                m = re.findall(r"'([^']+)'", source)
                if m:
                    # Filter obvious GUID-like tokens or keep all; we'll dedupe later
                    ids.extend(m)

        # Fallback: parse from page source via menuid=...
        if not ids:
            html_src = driver.page_source
            ids.extend(re.findall(r"menuid=([^'\"\s>&]+)", html_src))
            # Also match openSuburbanMenu('...') calls
            ids.extend(re.findall(r"openSuburbanMenu\('([^']+)'\)", html_src))

        # Deduplicate while preserving order
        seen = set()
        deduped: List[str] = []
        for mid in ids:
            if mid and mid not in seen:
                seen.add(mid)
                deduped.append(mid)
        return deduped
    finally:
        driver.quit()


def parse_items(doc: html.HtmlElement, category_hint: str | None = None) -> List[Dict]:
    records: List[Dict] = []
    category = (doc.xpath('.//div[@class="visible-small"]/preceding-sibling::table//span/text()') or [None])[0]
    if not category:
        category = category_hint
    items = doc.xpath('.//div[@class="menuItem"]')
    for item in items:
        nutrients = item.xpath('.//span[@style="margin: 6px"]/text()')
        if nutrients:
            kj = (nutrients[0].split('/') + [None, None])[0]
            kcal = (nutrients[0].split('/') + [None, None])[1]
            fat = nutrients[1] if len(nutrients) > 1 else None
            satfat = nutrients[2] if len(nutrients) > 2 else None
            carb = nutrients[3] if len(nutrients) > 3 else None
            sugar = nutrients[4] if len(nutrients) > 4 else None
            protein = nutrients[5] if len(nutrients) > 5 else None
            salt = nutrients[6] if len(nutrients) > 6 else None
        else:
            kj = kcal = fat = satfat = carb = sugar = protein = salt = None
        records.append({
            'collection_date': date.today().strftime('%b-%d-%Y'),
            'rest_name': REST_NAME,
            'menu_section': category,
            'item_name': (item.xpath('./p/span[1]/text()') or [''])[0],
            'item_description': (item.xpath('./p/span[2]/text()') or [''])[0],
            'allergens': (item.xpath('./p/span[3]/text()') or [''])[0],
            'kj': kj,
            'kcal': kcal,
            'fat': fat,
            'satfat': satfat,
            'carb': carb,
            'sugar': sugar,
            'protein': protein,
            'salt': salt,
        })
    return records


def selenium_click_and_parse() -> List[Dict]:
    """Navigate the brand page, click each menu link, and parse visible items."""
    driver = setup_driver()
    collected: List[Dict] = []
    try:
        # Desktop setup
        try:
            driver.set_window_size(1280, 900)
        except Exception:
            pass
        DESKTOP_UA = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        try:
            driver.execute_cdp_cmd('Network.enable', {})
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {'userAgent': DESKTOP_UA})
        except Exception:
            pass

        driver.get(LIST_URL)
        # Cookie banner
        try:
            cookie_btn = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ACCEPTALLOWAGREE', 'acceptallowagree'), 'accept') or contains(translate(., 'ACCEPTALLOWAGREE', 'acceptallowagree'), 'allow') or contains(translate(., 'ACCEPTALLOWAGREE', 'acceptallowagree'), 'agree') ]"))
            )
            driver.execute_script("arguments[0].click();", cookie_btn)
        except TimeoutException:
            pass

        # Wait for menu list
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'hidden-small')]//ul//li//a"))
            )
        except TimeoutException:
            # Fall back to any anchors
            pass

        # Gather anchors, re-query each iteration to avoid staleness
        index = 1
        while True:
            anchors = driver.find_elements(By.XPATH, "//div[contains(@class,'hidden-small')]//ul//li//a")
            if not anchors or index > len(anchors):
                break
            a = anchors[index - 1]
            menu_title = a.text.strip() or None
            # Click via JS to trigger AJAX load
            try:
                driver.execute_script("arguments[0].click();", a)
            except Exception:
                index += 1
                continue

            # Wait for menu items to appear
            try:
                WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@class='menuItem']"))
                )
            except TimeoutException:
                pass

            # Parse current DOM
            doc = html.fromstring(driver.page_source)
            recs = parse_items(doc, category_hint=menu_title)
            collected.extend(recs)
            index += 1

        return collected
    finally:
        driver.quit()


def save_outputs(records: List[Dict]):
    df = pd.DataFrame(records)
    df.to_csv(file_csv, index=False)
    df.to_json(file_json, orient='records')
    df.to_json(file_jsonl, orient='records', lines=True)
    print(f"Saved {len(df)} items to:\n- {file_json}\n- {file_jsonl}\n- {file_csv}")


def main():
    # Try static first
    doc = fetch_tree(LIST_URL)
    menuids = extract_menu_ids(doc)
    if not menuids:
        print("[info] No menu ids via requests; trying Selenium")
        menuids = extract_menu_ids_selenium()
    all_records: List[Dict] = []
    if menuids:
        print(f"Found {len(menuids)} menu id(s)")
        for i, mid in enumerate(menuids, 1):
            url = ITEMS_URL.format(menuid=mid)
            print(f"[{i}/{len(menuids)}] Fetching items: {url}")
            sub_doc = fetch_tree(url)
            recs = parse_items(sub_doc)
            print(f"[{i}/{len(menuids)}] Parsed {len(recs)} items")
            all_records.extend(recs)
    else:
        print("[info] Falling back to Selenium click-through parsing")
        all_records = selenium_click_and_parse()
    save_outputs(all_records)


if __name__ == '__main__':
    main()
