"""
Costa Coffee Menu Scraper (Selenium-only)

Scrapes menu items, nutritional information, allergens, and ingredients from
https://www.costa.co.uk/menu using Selenium browser automation.

Collects every product link from the menu page (the site is a list of links
to per-product pages, not an in-page modal), then visits each product page,
expands its Allergens / Ingredients / Nutritional Information accordions and
parses the tables inside.

Usage:
    python 3_CostaCoffee_selenium.py          # standalone
    %run 3_CostaCoffee_selenium.py            # from Jupyter / menutracker.ipynb
"""

import json
import logging
import os
import re
from datetime import date
from time import sleep
from urllib.parse import urlparse
from typing import List, Dict, Optional

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException

from define_collection_wave import folder, create_collection
from helpers import (
    create_folder, setup_driver, try_click_accept_cookies, clean_text, safe_get,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if folder is None:
    create_collection("Feb_collection_2026")
    from define_collection_wave import folder

REST_NAME = "CostaCoffee"
path_out = create_folder("3_CostaCoffee", folder)
file_json = os.path.join(path_out, "costacoffee_nutrition.json")
file_csv = os.path.join(path_out, "costacoffee_nutrition.csv")

MENU_URL = "https://www.costa.co.uk/menu"

WAIT_SHORT = 0.3
WAIT_MEDIUM = 0.8
WAIT_LONG = 2.0


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _js_click(driver, element) -> None:
    """Scroll into view and click via JS to avoid interception issues."""
    driver.execute_script(
        "arguments[0].scrollIntoView({block: 'center'});", element
    )
    sleep(0.3)
    driver.execute_script("arguments[0].click();", element)


def _scroll_to_load(driver, scrolls: int = 10) -> None:
    """Scroll down in steps to trigger lazy-loaded product links."""
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, 900);")
        sleep(0.4)
    driver.execute_script("window.scrollTo(0, 0);")
    sleep(WAIT_SHORT)


# ---------------------------------------------------------------------------
# Product discovery
# ---------------------------------------------------------------------------

def _product_links(driver) -> List[str]:
    """Unique /menu/<slug> product URLs currently present on the page."""
    _scroll_to_load(driver)
    hrefs = driver.execute_script(
        "return [...document.querySelectorAll('a[href*=\"/menu/\"]')].map(a => a.href);"
    )
    urls: List[str] = []
    for href in hrefs:
        path = urlparse(href).path.rstrip("/")
        if path.startswith("/menu/") and href not in urls:
            urls.append(href)
    return urls


def collect_product_urls(driver) -> Dict[str, str]:
    """Return {url: category}. The default view lists every product; the
    'All drinks' tab identifies the drinks, so the rest are food."""
    urls = _product_links(driver)
    drinks: set = set()
    for btn in driver.find_elements(By.TAG_NAME, "button"):
        try:
            if btn.is_displayed() and btn.text.strip().lower() == "all drinks":
                _js_click(driver, btn)
                sleep(WAIT_LONG)
                drinks = set(_product_links(driver))
                break
        except Exception:
            continue
    return {u: ("Drinks" if u in drinks else "Food") for u in urls}


# ---------------------------------------------------------------------------
# Data extraction from a product page
# ---------------------------------------------------------------------------

def _expand_accordion(driver, label: str) -> str:
    """Click the accordion button containing *label*; return the text of the
    panel it controls ("" if there is no such accordion)."""
    try:
        btn = driver.find_element(By.XPATH, f"//button[contains(., '{label}')]")
    except NoSuchElementException:
        return ""
    if btn.get_attribute("aria-expanded") != "true":
        _js_click(driver, btn)
        sleep(0.6)
    panel_id = btn.get_attribute("aria-controls")
    if panel_id:
        try:
            return clean_text(driver.find_element(By.ID, panel_id).text.strip())
        except NoSuchElementException:
            pass
    return ""


_TABLE_ROWS_JS = (
    "return [...arguments[0].querySelectorAll('tr')]"
    ".map(r => [...r.children].map(c => c.innerText.trim()));"
)


def parse_allergen_rows(rows: List[List[str]]) -> Dict[str, str]:
    """Rows of [label, value] -> {'Milk Products': 'Yes', ...}."""
    return {r[0]: r[1] for r in rows if len(r) >= 2 and r[0]}


def parse_nutrition_rows(rows: List[List[str]]) -> Dict[str, str]:
    """Rows with a header row ['', 'Per 100g/ml', 'In Store (384ml)', ...] and
    one [label, *values] row per nutrient -> flat {'<label>_<column>': value}.
    The column's size in brackets is dropped from the key and kept once as
    Portion_Size, so keys are identical across products."""
    result: Dict[str, str] = {}
    columns: List[str] = []
    for row in rows:
        if not row:
            continue
        if not row[0] and len(row) > 1:
            columns = []
            for head in row[1:]:
                size = re.search(r"\(([^)]+)\)", head)
                if size:
                    result.setdefault("Portion_Size", size.group(1))
                columns.append(re.sub(r"\s*\(.*?\)", "", head).strip())
        elif columns:
            for column, value in zip(columns, row[1:]):
                result[f"{row[0]}_{column}"] = value
    return result


def _page_tables(driver):
    """Return (allergen_rows, nutrition_rows) from the visible tables."""
    allergens: List[List[str]] = []
    nutrition: List[List[str]] = []
    for tbl in driver.find_elements(By.TAG_NAME, "table"):
        if not tbl.is_displayed():
            continue
        rows = driver.execute_script(_TABLE_ROWS_JS, tbl)
        if any("Per 100g" in cell for row in rows for cell in row):
            nutrition = nutrition or rows
        else:
            allergens = allergens or rows
    return allergens, nutrition


def extract_product(driver, url: str, category: str) -> Optional[Dict]:
    """Return the record for the product page already loaded in driver, or None if it has no name."""
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
    name = clean_text(driver.find_element(By.TAG_NAME, "h1").text.strip())
    if not name:
        return None

    _expand_accordion(driver, "Allergens Information")
    ingredients = _expand_accordion(driver, "Ingredients")
    _expand_accordion(driver, "Nutritional Information")

    allergen_rows, nutrition_rows = _page_tables(driver)
    record: Dict = {
        "collection_date": date.today().strftime("%b-%d-%Y"),
        "rest_name": REST_NAME,
        "Product_Name": name,
        "Category": category,
        "Product_URL": url,
        "Ingredients": ingredients,
    }
    for k, v in parse_allergen_rows(allergen_rows).items():
        record[f"Allergen_{k}"] = v
    record.update(parse_nutrition_rows(nutrition_rows))
    return record


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def _fresh_driver(old):
    """Replace a wedged browser with a new one that has the cookie banner dismissed."""
    try:
        old.quit()
    except Exception:
        pass
    driver = setup_driver()
    driver.set_page_load_timeout(60)
    driver = safe_get(driver, MENU_URL)
    sleep(WAIT_LONG)
    try_click_accept_cookies(driver)
    return driver


def scrape_costa_menu() -> List[Dict]:
    """Launch browser, scrape every product page, return all records."""
    logger.info("Launching browser…")
    driver = setup_driver()
    driver.set_page_load_timeout(60)
    items: List[Dict] = []
    failed: List[str] = []

    try:
        logger.info(f"Navigating to {MENU_URL}")
        driver = safe_get(driver, MENU_URL)
        sleep(WAIT_LONG + 3)
        try_click_accept_cookies(driver)
        sleep(WAIT_MEDIUM)

        products = collect_product_urls(driver)
        logger.info(f"Found {len(products)} product pages")

        for idx, (url, category) in enumerate(products.items(), 1):
            for attempt in (1, 2):
                try:
                    driver = safe_get(driver, url)
                    record = extract_product(driver, url, category)
                    if record:
                        items.append(record)
                        logger.info(f"[{idx}/{len(products)}] {record['Product_Name']}")
                    break
                except Exception as exc:
                    # A wedged renderer ("Timed out receiving message from renderer")
                    # makes every later page crawl, so retry once in a fresh browser.
                    if attempt == 1:
                        logger.warning(f"[{idx}/{len(products)}] {url}: {exc}; restarting browser")
                        driver = _fresh_driver(driver)
                    else:
                        failed.append(url)
                        logger.error(f"[{idx}/{len(products)}] {url}: {exc}")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    if failed:
        logger.warning(f"{len(failed)} product page(s) failed: {failed[:5]}")
    return items


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_results(items: List[Dict], json_path: str, csv_path: str) -> None:
    if not items:
        raise RuntimeError("No Costa products scraped (bot block or site change); nothing to save")

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(items, fh, indent=2, ensure_ascii=False)
    logger.info(f"JSON saved → {json_path}  ({len(items)} items)")

    df = pd.DataFrame(items)
    df.to_csv(csv_path, index=False, encoding="utf-8")
    logger.info(f"CSV  saved → {csv_path}  ({len(items)} items)")

    print(f"\n{'=' * 60}")
    print(f"Costa Coffee scrape complete — {len(items)} items")
    print(f"  JSON: {json_path}")
    print(f"  CSV:  {csv_path}")
    print(f"{'=' * 60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    logger.info("=== Costa Coffee Selenium Scraper ===")
    items = scrape_costa_menu()
    save_results(items, file_json, file_csv)
    return items


if __name__ == "__main__":
    main()
