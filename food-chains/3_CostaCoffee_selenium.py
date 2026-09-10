"""
Costa Coffee Menu Scraper (Selenium-only)

Scrapes menu items, nutritional information, allergens, and ingredients from
https://www.costa.co.uk/menu using Selenium browser automation.

Navigates Drinks and Food tabs, opens each product's detail panel, expands
the Allergens / Ingredients / Nutritional Information accordions, and parses
the tables inside.

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
from typing import List, Dict, Optional

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
)

from define_collection_wave import folder, create_collection
from helpers import (
    create_folder, setup_driver, try_click_accept_cookies, clean_text,
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


def _close_product_view(driver) -> None:
    """Close the product detail overlay."""
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "[class*='CloseButton']")
        if btn.is_displayed():
            _js_click(driver, btn)
            sleep(WAIT_SHORT)
            return
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        sleep(WAIT_SHORT)
    except Exception:
        pass


def _scroll_to_load(driver, scrolls: int = 8) -> None:
    """Scroll down in steps to trigger lazy-loaded product cards."""
    for _ in range(scrolls):
        driver.execute_script("window.scrollBy(0, 800);")
        sleep(0.5)
    driver.execute_script("window.scrollTo(0, 0);")
    sleep(WAIT_SHORT)


# ---------------------------------------------------------------------------
# Element finders
# ---------------------------------------------------------------------------

def _find_product_cards(driver) -> List[Dict]:
    """
    Return list of {'name': str, 'element': WebElement} for each visible
    product card on the page.
    """
    cards = driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
    results = []
    for card in cards:
        if not card.is_displayed():
            continue
        name = card.text.strip()
        if name and len(name) > 1:
            results.append({"name": name, "element": card})
    return results


def _find_subcategory_buttons(driver, tab_name: str) -> List[Dict]:
    """
    Best-effort discovery of subcategory chips under the selected tab.
    Returns [{'name': str, 'element': WebElement}, ...].
    """
    skip_exact = {
        "drinks",
        "food",
        "our menu",
        "order now",
        "vegetarian",
        "vegan",
        "clear",
        "milk",
        "tree nut",
        "peanut",
        "soybeans",
        "sesame",
        "gluten",
        "eggs",
        "sulphites",
        "show full allergens list",
    }
    skip_contains = {
        "costa club",
        "gift cards",
        "sustainability",
        "for business",
        "contact us",
    }

    found: List[Dict] = []
    seen = set()
    candidates = driver.find_elements(By.CSS_SELECTOR, "button")
    for btn in candidates:
        try:
            if not btn.is_displayed():
                continue
            text = clean_text(btn.text)
            ltxt = text.lower()
            if (
                not text
                or len(text) > 35
                or ltxt == tab_name.lower()
                or ltxt in skip_exact
                or any(token in ltxt for token in skip_contains)
            ):
                continue

            # Keep only controls in the upper menu area, not item cards.
            y = btn.location.get("y", 9999)
            if y > 520:
                continue

            if ltxt not in seen:
                seen.add(ltxt)
                found.append({"name": text, "element": btn})
        except Exception:
            continue

    return found


# ---------------------------------------------------------------------------
# Data extraction from the product detail panel
# ---------------------------------------------------------------------------

def _expand_accordion(driver, modal, label: str) -> bool:
    """Click an accordion button whose text contains *label*. Return True if found."""
    try:
        btn = modal.find_element(
            By.XPATH, f".//button[contains(., '{label}')]"
        )
        if btn.is_displayed():
            _js_click(driver, btn)
            sleep(0.5)
            return True
    except NoSuchElementException:
        pass
    return False


def _extract_description(modal) -> str:
    try:
        el = modal.find_element(By.CSS_SELECTOR, "[class*='ProductDescription']")
        return clean_text(el.text.strip())
    except NoSuchElementException:
        return ""


def _extract_allergen_table(modal) -> Dict[str, str]:
    """
    Parse the allergen table (first <table> that does NOT contain
    'Per 100g' in its text). Returns e.g. {'Milk Products': 'Yes'}.
    """
    allergens: Dict[str, str] = {}
    try:
        tables = modal.find_elements(By.TAG_NAME, "table")
        for tbl in tables:
            if not tbl.is_displayed():
                continue
            text = tbl.text
            if "Per 100g" in text or "Per Portion" in text:
                continue
            rows = tbl.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:
                    key = cells[0].text.strip()
                    val = cells[1].text.strip()
                    if key:
                        allergens[key] = val
            if allergens:
                break
    except Exception:
        pass
    return allergens


def _extract_nutrition_table(modal) -> Dict[str, str]:
    """
    Parse the nutrition table (the <table> whose text includes 'Per 100g').
    Returns flat dict like {'Energy (kJ)_Per 100g/ml': '176', ...}.
    """
    nutrition: Dict[str, str] = {}
    try:
        tables = modal.find_elements(By.TAG_NAME, "table")
        for tbl in tables:
            if not tbl.is_displayed():
                continue
            if "Per 100g" not in tbl.text:
                continue
            rows = tbl.find_elements(By.TAG_NAME, "tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:
                    key = cells[0].text.strip()
                    if not key:
                        continue
                    nutrition[f"{key}_Per 100g/ml"] = cells[1].text.strip()
                    if len(cells) >= 3:
                        nutrition[f"{key}_Per Portion"] = cells[2].text.strip()
            break
    except Exception:
        pass
    return nutrition


def _extract_ingredients(modal) -> str:
    """
    Return the ingredients text. The Ingredients accordion content sits
    right after the accordion button; we grab the accordion content div.
    """
    for sel in [
        "[class*='AccordionContent']",
        "[class*='ccordion'] div",
    ]:
        try:
            elems = modal.find_elements(By.CSS_SELECTOR, sel)
            for e in elems:
                text = e.text.strip()
                # Ingredients text is typically long and contains commas
                if e.is_displayed() and len(text) > 30 and "," in text:
                    if "allergen" not in text.lower()[:30] and "Per 100g" not in text:
                        return clean_text(text)
        except Exception:
            continue
    return ""


def extract_product_detail(driver, modal) -> Dict:
    """
    With the product view open, expand all accordions and extract
    description, allergens, ingredients, and nutrition.
    """
    description = _extract_description(modal)

    _expand_accordion(driver, modal, "Allergens Information")
    _expand_accordion(driver, modal, "Ingredients")
    _expand_accordion(driver, modal, "Nutritional Information")

    allergens = _extract_allergen_table(modal)
    ingredients = _extract_ingredients(modal)
    nutrition = _extract_nutrition_table(modal)

    record: Dict = {
        "Product_Description": description,
        "Ingredients": ingredients,
    }
    for k, v in allergens.items():
        record[f"Allergen_{k}"] = v
    record.update(nutrition)
    return record


# ---------------------------------------------------------------------------
# Tab / category scraping
# ---------------------------------------------------------------------------

def _scrape_tab(driver, tab_name: str, processed: set) -> List[Dict]:
    """Scrape all products under one top-level tab (Drinks / Food)."""
    items: List[Dict] = []

    try:
        tab_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable(
                (By.XPATH, f"//button[contains(., '{tab_name}')]")
            )
        )
    except TimeoutException:
        logger.warning(f"Tab button '{tab_name}' not found")
        return items

    _js_click(driver, tab_btn)
    sleep(WAIT_LONG)

    subcategories = _find_subcategory_buttons(driver, tab_name)
    if not subcategories:
        subcategories = [{"name": tab_name, "element": None}]
        logger.info(f"No subcategory controls detected for '{tab_name}'")
    else:
        logger.info(f"Detected {len(subcategories)} subcategories for '{tab_name}'")

    for sub in subcategories:
        sub_name = sub["name"]
        sub_el = sub["element"]
        logger.info(f"  Subcategory: {sub_name}")

        if sub_el is not None:
            try:
                _js_click(driver, sub_el)
                sleep(WAIT_MEDIUM)
            except Exception:
                # Re-find by text in case of stale element
                try:
                    ref = driver.find_element(By.XPATH, f"//button[contains(., '{sub_name}')]")
                    _js_click(driver, ref)
                    sleep(WAIT_MEDIUM)
                except Exception:
                    logger.warning(f"  Could not click subcategory '{sub_name}', skipping")
                    continue

        _scroll_to_load(driver)
        cards = _find_product_cards(driver)
        total = len(cards)
        logger.info(f"Found {total} products under '{sub_name}'")

        for idx in range(total):
            fresh = _find_product_cards(driver)
            if idx >= len(fresh):
                logger.warning(f"Product list shrank ({len(fresh)} < {idx + 1}), stopping")
                break

            card = fresh[idx]
            product_name = card["name"]

            if product_name in processed:
                continue
            processed.add(product_name)

            logger.info(f"  [{idx + 1}/{total}] {product_name}")

            try:
                _js_click(driver, card["element"])
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "[class*='ProductView']")
                        )
                    )
                except TimeoutException:
                    logger.debug(f"ProductView wait timed out for {product_name}")
                sleep(WAIT_MEDIUM)

                modal = driver.find_element(By.CSS_SELECTOR, "[class*='ProductView']")
                detail = extract_product_detail(driver, modal)

                record = {
                    "collection_date": date.today().strftime("%b-%d-%Y"),
                    "rest_name": REST_NAME,
                    "Product_Name": product_name,
                    "Category": tab_name,
                    "Subcategory": sub_name,
                }
                record.update(detail)
                items.append(record)

                has_nut = any("Per 100g" in k for k in detail)
                has_alg = any(k.startswith("Allergen_") for k in detail)
                has_ing = bool(detail.get("Ingredients"))
                logger.info(
                    f"    nutrition={'yes' if has_nut else 'no'}  "
                    f"allergens={'yes' if has_alg else 'no'}  "
                    f"ingredients={'yes' if has_ing else 'no'}"
                )

                _close_product_view(driver)

            except StaleElementReferenceException:
                logger.warning(f"  Stale element for {product_name}, skipping")
                _close_product_view(driver)
            except Exception as exc:
                logger.error(f"  Error processing {product_name}: {exc}")
                _close_product_view(driver)

    return items


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

def scrape_costa_menu() -> List[Dict]:
    """Launch browser, scrape Drinks + Food tabs, return all records."""
    logger.info("Launching browser…")
    driver = setup_driver()
    driver.set_page_load_timeout(60)
    all_items: List[Dict] = []
    processed: set = set()

    try:
        logger.info(f"Navigating to {MENU_URL}")
        try:
            driver.get(MENU_URL)
        except TimeoutException:
            logger.warning("Page load timed out; continuing anyway")
        sleep(WAIT_LONG + 3)

        try_click_accept_cookies(driver)
        sleep(WAIT_MEDIUM)

        for tab in ["Drinks", "Food"]:
            logger.info(f"{'=' * 50}")
            logger.info(f"  TAB: {tab}")
            logger.info(f"{'=' * 50}")
            tab_items = _scrape_tab(driver, tab, processed)
            all_items.extend(tab_items)
            logger.info(
                f"Collected {len(tab_items)} from {tab} "
                f"(running total: {len(all_items)})"
            )

    except Exception as exc:
        logger.error(f"Fatal error: {exc}", exc_info=True)
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return all_items


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_results(items: List[Dict], json_path: str, csv_path: str) -> None:
    if not items:
        logger.error("No items scraped — nothing to save.")
        return

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
