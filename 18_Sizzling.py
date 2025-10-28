import re
import json
from datetime import date

import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from define_collection_wave import folder
from helpers import create_folder, setup_driver

# Output paths (match project convention like 14_CaffeNero.py)
path_sizzling = create_folder('18_Sizzling', folder)
file_sizzling_json = path_sizzling + '/sizzling_items.json'
file_sizzling_csv = path_sizzling + '/sizzling_items.csv'

# Target Sizzling Pubs menu pages ONLY (no smartchef)
SIZZLING_MENU_PAGES = {
    'Main': 'https://www.sizzlingpubs.co.uk/food-menu',
    'Breakfast': 'https://www.sizzlingpubs.co.uk/breakfastmenu',
    'Kids': 'https://www.sizzlingpubs.co.uk/kidsmenu',
    'Buffet': 'https://www.sizzlingpubs.co.uk/buffetmenu',
    'Drinks': 'https://www.sizzlingpubs.co.uk/drink',
    'Sunday': 'https://www.sizzlingpubs.co.uk/sunday-menu',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
}


def _flatten_jsonld(node):
    """Yield all dict nodes inside a json-ld structure."""
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _flatten_jsonld(v)
    elif isinstance(node, list):
        for it in node:
            yield from _flatten_jsonld(it)


def parse_jsonld_items(html: str, *, menu_name: str, source_url: str) -> list[dict]:
    """Parse JSON-LD for Menu/MenuSection/MenuItem/Product entries.

    Returns minimal nutrition (kcal) if present and captures name/description.
    Allergens are rarely exposed in JSON-LD on these pages but we include placeholders.
    """
    items: list[dict] = []
    soup = BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            data = json.loads(script.string or '{}')
        except Exception:
            continue
        for obj in _flatten_jsonld(data):
            t = obj.get('@type')
            if not t:
                continue
            if isinstance(t, list):
                types = set(t)
            else:
                types = {t}
            if {'MenuItem', 'Product'} & types:
                name = obj.get('name')
                desc = obj.get('description')
                nutrition = obj.get('nutrition') or {}
                kcal = nutrition.get('calories') or nutrition.get('calorieContent')
                # Normalise '123 kcal' → '123'
                if isinstance(kcal, str):
                    m = re.search(r"(\d[\d,]*)", kcal)
                    kcal = m.group(1).replace(',', '') if m else kcal

                items.append({
                    'collection_date': date.today().strftime("%b-%d-%Y"),
                    'rest_name': 'Sizzling Pubs',
                    'menu_id': None,
                    'menu_section': menu_name,
                    'item_name': name,
                    'item_description': desc,
                    'allergens': None,  # not in JSON-LD typically
                    'kj': None,
                    'kcal': kcal,
                    'fat': nutrition.get('fatContent'),
                    'satfat': nutrition.get('saturatedFatContent'),
                    'carb': nutrition.get('carbohydrateContent'),
                    'sugar': nutrition.get('sugarContent'),
                    'protein': nutrition.get('proteinContent'),
                    'salt': nutrition.get('sodiumContent') or nutrition.get('salt'),
                    'source_url': source_url,
                })
    return items

def _try_click_accept_cookies(driver) -> None:
    """Attempt to accept cookies banner to unblock interactions."""
    try:
        # Try several common selectors/texts
        candidates = [
            (By.XPATH, "//button[contains(translate(., 'ACCEPT', 'accept'), 'accept')]") ,
            (By.XPATH, "//a[contains(translate(., 'ACCEPT', 'accept'), 'accept')]") ,
            (By.XPATH, "//button[contains(., 'ACCEPT ALL COOKIES') or contains(., 'Accept All Cookies')]") ,
        ]
        for by, sel in candidates:
            elems = driver.find_elements(by, sel)
            if elems:
                try:
                    elems[0].click()
                    WebDriverWait(driver, 2).until(lambda d: True)
                    break
                except Exception:
                    continue
    except Exception:
        pass


def _extract_from_dialog(driver) -> dict:
    """Best-effort extraction of nutrition/allergen details from an open modal/dialog."""
    details = {
        'allergens': None,
        'kj': None,
        'kcal': None,
        'fat': None,
        'satfat': None,
        'carb': None,
        'sugar': None,
        'protein': None,
        'salt': None,
    }
    try:
        # Wait for a dialog/modal; try multiple patterns
        dialog = None
        patterns = [
            (By.XPATH, "//*[@role='dialog']"),
            (By.XPATH, "//*[contains(@class,'modal') or contains(@class,'Dialog')]")
        ]
        for by, xp in patterns:
            try:
                dialog = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((by, xp))
                )
                if dialog:
                    break
            except TimeoutException:
                continue
        if not dialog:
            return details

        text = dialog.text or ''
        # kcal/kJ
        m_kcal = re.search(r"(\d[\d,]*)\s*kcal", text, flags=re.I)
        if m_kcal:
            details['kcal'] = m_kcal.group(1).replace(',', '')
        m_kj = re.search(r"(\d[\d,]*)\s*k[jJ]", text)
        if m_kj:
            details['kj'] = m_kj.group(1).replace(',', '')

        # Common macro labels; capture first number and units
        def cap(label, key):
            m = re.search(label + r"\s*:?\s*([\d,.]+\s*[a-zA-Z%/]*)", text, flags=re.I)
            if m:
                details[key] = m.group(1).strip()
        cap(r"fat", 'fat')
        cap(r"saturates|sat\.?\s*f(at)?", 'satfat')
        cap(r"carb(ohydrate|s)?", 'carb')
        cap(r"sugar(s)?", 'sugar')
        cap(r"protein", 'protein')
        cap(r"salt|sodium", 'salt')

        # Allergens
        m_all = re.search(r"allergen[s]?:?\s*(.+)", text, flags=re.I)
        if m_all:
            # stop at newline
            details['allergens'] = m_all.group(1).split('\n')[0].strip()

        # Try close dialog to proceed
        for sel in [
            (By.XPATH, "//button[@aria-label='Close' or contains(., 'Close')]"),
            (By.XPATH, "//*[contains(@class,'close') and (self::button or self::a)]"),
        ]:
            try:
                btns = dialog.find_elements(*sel)
                if btns:
                    btns[0].click()
                    break
            except Exception:
                continue
    except Exception:
        pass
    return details


def parse_menu_with_selenium(menu_name: str, url: str) -> list[dict]:
    driver = setup_driver()
    records: list[dict] = []
    try:
        driver.get(url)
        _try_click_accept_cookies(driver)

        # Wait for content to render; headings should appear
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h3, h4'))
        )
        headings = driver.find_elements(By.CSS_SELECTOR, 'h3, h4')
        seen_names = set()
        for h in headings:
            try:
                name = (h.text or '').strip()
                if not name or len(name) < 2:
                    continue
                # Heuristic: find kcal near heading
                kcal = None
                try:
                    container = h
                    for _ in range(3):
                        container = container.find_element(By.XPATH, "..")
                    txt = container.text
                    m = re.search(r"(\d[\d,]*)\s*kcal", txt, flags=re.I)
                    if m:
                        kcal = m.group(1).replace(',', '')
                except Exception:
                    pass

                # Attempt to open details modal and extract nutrition/allergens
                details = {
                    'allergens': None, 'kj': None, 'kcal': kcal,
                    'fat': None, 'satfat': None, 'carb': None, 'sugar': None, 'protein': None, 'salt': None,
                }
                clicked = False
                # Click nearest clickable ancestor
                try:
                    clickable = h.find_element(By.XPATH, "ancestor::*[self::a or self::button][1]")
                    driver.execute_script("arguments[0].click();", clickable)
                    clicked = True
                except Exception:
                    # try clicking the heading itself
                    try:
                        h.click()
                        clicked = True
                    except Exception:
                        pass

                if clicked:
                    extracted = _extract_from_dialog(driver)
                    # Prefer dialog kcal if found
                    for k, v in extracted.items():
                        if v is not None:
                            details[k] = v

                # Avoid duplicates (same name within menu)
                key = (menu_name, name)
                if key in seen_names:
                    continue
                seen_names.add(key)

                records.append({
                    'collection_date': date.today().strftime("%b-%d-%Y"),
                    'rest_name': 'Sizzling Pubs',
                    'menu_id': None,
                    'menu_section': menu_name,
                    'item_name': name,
                    'item_description': None,
                    'allergens': details['allergens'],
                    'kj': details['kj'],
                    'kcal': details['kcal'],
                    'fat': details['fat'],
                    'satfat': details['satfat'],
                    'carb': details['carb'],
                    'sugar': details['sugar'],
                    'protein': details['protein'],
                    'salt': details['salt'],
                    'source_url': url,
                })
            except Exception:
                continue
    finally:
        try:
            driver.quit()
        except Exception:
            pass
    return records


def scrape_sizzling() -> list[dict]:
    all_items: list[dict] = []
    for menu_name, url in SIZZLING_MENU_PAGES.items():
        # Selenium-first approach to allow interacting with per-dish details
        print(f"Processing menu: {menu_name} ({url})")
        items = parse_menu_with_selenium(menu_name, url)
        # If interaction failed to find anything, fall back to static parsing
        if not items:
            try:
                r = requests.get(url, headers=HEADERS, timeout=40)
                if r.status_code == 200:
                    html = r.text
                    items = parse_jsonld_items(html, menu_name=menu_name, source_url=url)
            except Exception:
                pass
        print(f"{menu_name}: found {len(items)} items")
        all_items.extend(items)
    return all_items


def main():
    results = scrape_sizzling()
    # Save results to CSV and JSON
    if results:
        df = pd.DataFrame(results)
        df.to_csv(file_sizzling_csv, index=False)
        print(f"Scraped {len(results)} items. Data saved to {file_sizzling_csv}.")
        with open(file_sizzling_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Scraped {len(results)} items. Data saved to {file_sizzling_json}.")
    else:
        print('No items found to save.')


if __name__ == '__main__':
    main()
