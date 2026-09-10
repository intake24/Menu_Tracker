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
from helpers import setup_driver

from define_collection_wave import folder
from helpers import create_folder, headers

REST_NAME = 'Browns'
BASE_URL = 'https://www.smartchef.co.uk'
START_URL = f'{BASE_URL}/brands/BrownsRestaurants'
SUBURBAN_URL = f'{BASE_URL}/Brands/SuburbanMenuItems?menuid={{menuid}}'

# Outputs
path_out = create_folder('89_Browns', folder)
file_json = os.path.join(path_out, 'browns_items.json')
file_jsonl = os.path.join(path_out, 'browns_items_JSONL.json')
file_csv = os.path.join(path_out, 'browns_items.csv')


def fetch_tree(url: str) -> html.HtmlElement:
    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()
    return html.fromstring(resp.text)


def fetch_text(url: str) -> str:
    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()
    return resp.text


def parse_menuids(doc: html.HtmlElement) -> List[str]:
    hrefs = doc.xpath('.//div[@class="hidden-small"]/div/ul/li/a/@href')
    menuids: List[str] = []
    for h in hrefs:
        # original spider extracted with a regex "'([^"]*)'" from href
        m = re.findall("'([^\"]*)'", h)
        if m:
            menuids.append(m[0])
    return menuids


def selenium_menuids() -> List[str]:
    ids: List[str] = []
    driver = setup_driver()
    try:
        # Force desktop layout and UA
        try:
            driver.set_window_size(1280, 900)
        except Exception:
            pass
        try:
            driver.execute_cdp_cmd('Network.enable', {})
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
        except Exception:
            pass
        driver.get(START_URL)
        # Accept any cookie banner if present
        try:
            WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ACCEPTALLOWAGREEOK', 'acceptallowagreeok'), 'accept') or contains(translate(., 'ACCEPTALLOWAGREEOK', 'acceptallowagreeok'), 'allow') or contains(translate(., 'ACCEPTALLOWAGREEOK', 'acceptallowagreeok'), 'agree') or contains(translate(., 'ACCEPTALLOWAGREEOK', 'acceptallowagreeok'), 'ok')]"))
            ).click()
        except TimeoutException:
            pass
        # Wait for the list to appear
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a'))
            )
        except TimeoutException:
            pass
        # Scroll to trigger any lazy content
        try:
            prev_h = driver.execute_script("return document.body.scrollHeight")
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                WebDriverWait(driver, 2).until(lambda d: True)
                h = driver.execute_script("return document.body.scrollHeight")
                if h == prev_h:
                    break
                prev_h = h
        except Exception:
            pass

        anchors = driver.find_elements(By.CSS_SELECTOR, 'a')
        for a in anchors:
            href = a.get_attribute('href') or ''
            onclick = a.get_attribute('onclick') or ''
            # Pattern 1: direct query param in href
            m1 = re.findall(r"SuburbanMenuItems\?menuid=([A-Za-z0-9\-]+)", href)
            if m1:
                ids.extend(m1)
                continue
            # Pattern 2: single-quoted arg in onclick handlers
            m2 = re.findall(r"'([^']+)'", onclick)
            if m2:
                ids.append(m2[0])

        # If still empty, regex scan the page source for any menuid patterns
        if not ids:
            src = driver.page_source
            ids.extend(re.findall(r"SuburbanMenuItems\?menuid=([A-Za-z0-9\-]+)", src))
            ids.extend(re.findall(r"menuid=['\"]?([A-Za-z0-9\-]+)['\"]?", src))
    finally:
        driver.quit()
    # De-duplicate while preserving order
    seen = set()
    uniq = []
    for i in ids:
        if i not in seen:
            uniq.append(i)
            seen.add(i)
    return uniq


def parse_items(doc: html.HtmlElement) -> List[Dict]:
    category = (doc.xpath('.//div[@class="visible-small"]/preceding-sibling::table//span/text()') or [''])[0]
    items = doc.xpath('.//div[@class="menuItem"]')
    out: List[Dict] = []
    for it in items:
        nutrients = it.xpath('.//span[@style="margin: 6px"]/text()')
        if nutrients:
            # Example format: "1234kJ/567kcal" then other fields follow in order
            first = nutrients[0]
            kj = first.split('/')[0] if '/' in first else first
            kcal = first.split('/')[1] if '/' in first and len(first.split('/')) > 1 else ''
            fat = nutrients[1] if len(nutrients) > 1 else ''
            satfat = nutrients[2] if len(nutrients) > 2 else ''
            carb = nutrients[3] if len(nutrients) > 3 else ''
            sugar = nutrients[4] if len(nutrients) > 4 else ''
            protein = nutrients[5] if len(nutrients) > 5 else ''
            salt = nutrients[6] if len(nutrients) > 6 else ''
        else:
            kj = kcal = fat = satfat = carb = sugar = protein = salt = ''
        out.append({
            'collection_date': date.today().strftime('%b-%d-%Y'),
            'rest_name': REST_NAME,
            'menu_section': category,
            'item_name': (it.xpath('./p/span[1]/text()') or [''])[0],
            'item_description': (it.xpath('./p/span[2]/text()') or [''])[0],
            'allergens': (it.xpath('./p/span[3]/text()') or [''])[0],
            'kj': kj,
            'kcal': kcal,
            'fat': fat,
            'satfat': satfat,
            'carb': carb,
            'sugar': sugar,
            'protein': protein,
            'salt': salt,
        })
    return out


def save_outputs(records: List[Dict]):
    df = pd.DataFrame(records)
    df.to_csv(file_csv, index=False)
    df.to_json(file_json, orient='records')
    df.to_json(file_jsonl, orient='records', lines=True)
    print(f"Saved {len(df)} items to:\n- {file_json}\n- {file_jsonl}\n- {file_csv}")


def main():
    # Try static discovery first
    try:
        start_doc = fetch_tree(START_URL)
        ids = parse_menuids(start_doc)
    except Exception:
        ids = []
    # If XPath discovery failed, try regex extraction on raw HTML
    if not ids:
        try:
            html_text = fetch_text(START_URL)
            # Direct menuid query param occurrences
            ids.extend(re.findall(r"SuburbanMenuItems\?menuid=([A-Za-z0-9\-]+)", html_text))
            # Generic menuid assignments
            ids.extend(re.findall(r"menuid=['\"]?([A-Za-z0-9\-]{6,})['\"]?", html_text))
            # openMenu calls, GUID-like second parameter
            ids.extend(re.findall(r"openMenu\([^\)]*?['\"]([0-9a-fA-F\-]{6,})['\"]", html_text))
            # Deduplicate maintain order
            seen = set()
            ids = [x for x in ids if not (x in seen or seen.add(x))]
        except Exception:
            pass
    if not ids:
        print('[info] Static discovery returned 0 ids; trying Selenium fallback')
        ids = selenium_menuids()
    print(f"[info] Found {len(ids)} menu id(s)")

    all_records: List[Dict] = []
    for idx, menuid in enumerate(ids, start=1):
        url = SUBURBAN_URL.format(menuid=menuid)
        print(f"[fetch {idx}/{len(ids)}] {url}")
        try:
            doc = fetch_tree(url)
            recs = parse_items(doc)
        except Exception:
            recs = []
        # If requests path failed or returned nothing, try Selenium render as fallback
        if not recs:
            driver = setup_driver()
            try:
                try:
                    driver.set_window_size(1280, 900)
                except Exception:
                    pass
                driver.get(url)
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.menuItem'))
                    )
                except TimeoutException:
                    pass
                tree = html.fromstring(driver.page_source)
                recs = parse_items(tree)
            finally:
                driver.quit()
        print(f"[parse {idx}/{len(ids)}] {len(recs)} items")
        all_records.extend(recs)

    save_outputs(all_records)


if __name__ == '__main__':
    main()
