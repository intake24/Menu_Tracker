import os
import time
import json
import re
from datetime import date
from typing import List, Dict, Tuple

import pandas as pd
from lxml import html

from define_collection_wave import folder
from helpers import create_folder, setup_driver

from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException, NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait

import requests


REST_NAME = 'Cafe Rouge'
LANDING_URL = 'https://www.caferouge.com/restaurants/Center-Parcs/elveden/menu'
BASE_DOMAIN = 'https://www.caferouge.com'

# Outputs
path_out = create_folder('82_CafeRouge', folder)
file_json = os.path.join(path_out, 'cafe_rouge_items.json')
file_jsonl = os.path.join(path_out, 'cafe_rouge_items_JSONL.json')
file_csv = os.path.join(path_out, 'cafe_rouge_items.csv')


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


def accept_cookies(driver) -> bool:
    try:
        for xp in [
            "//button[contains(translate(., 'ACCEPT', 'accept'),'accept')]",
            "//button[contains(., 'Accept All')]",
            "//button[contains(., 'Accept')]",
            "//a[contains(., 'Accept All')]",
        ]:
            btns = driver.find_elements(By.XPATH, xp)
            for b in btns:
                try:
                    driver.execute_script("arguments[0].click();", b)
                    time.sleep(0.5)
                    print("Accepted cookies")
                    return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def extract_menu_guids(tree) -> list[tuple[str, str]]:
    """Extract (menu_name, guid) tuples from the Ten Kites selector options."""
    pairs: list[tuple[str, str]] = []
    options = tree.xpath('(//div[contains(@class, "k10-menu-selector__options")])[1]/div[contains(@class, "k10-menu-selector__option")]')
    guid_re = re.compile(r'[0-9a-fA-F\-]{36}')
    seen: set[str] = set()
    for i, opt in enumerate(options):
        name = get_text(opt, './/span/span/text()')
        guid = ''
        snip = html.tostring(opt, encoding='unicode')
        m = guid_re.search(snip)
        if m:
            guid = m.group(0)
        if name and guid and guid not in seen:
            seen.add(guid)
            pairs.append((name.strip(), guid))
    return pairs


def wait_for_menu_pairs(driver, timeout: int = 15) -> list[tuple[str, str]]:
    """Wait for the client-rendered Ten Kites menu selector."""
    try:
        return WebDriverWait(driver, timeout).until(
            lambda current_driver: extract_menu_guids(
                html.fromstring(current_driver.page_source)
            )
        )
    except Exception:
        return extract_menu_guids(html.fromstring(driver.page_source))


def extract_items_from_html(page_source: str, menu_name: str) -> List[Dict]:
    """Parse Ten Kites rendered menu HTML without attempting JS clicks.
    Captures recipe cards and BYO (build-your-own) items.
    """
    tree = html.fromstring(page_source)
    results: List[Dict] = []

    # Section context: preceding section headers within k10 layout columns
    # Ten Kites often wraps sections in div.k10-menu-section-header or similar
    # We'll map each card to the nearest preceding h2/h3/span with section semantics
    section_headers = tree.xpath('//h2|//h3|//div[contains(@class,"k10-menu-section-header")]//h2|//div[contains(@class,"k10-menu-section-header")]//h3')

    def nearest_section(node) -> str:
        try:
            # look backwards among previous elements
            prev = node.xpath('(preceding::h2 | preceding::h3)[1]/text()')
            if prev:
                return prev[0].strip()
        except Exception:
            pass
        return ''

    # Recipe cards
    recipe_cards = tree.xpath('//div[contains(@class,"k10-menu-item-card") and .//span[contains(@class,"k10-recipe__name")]]')
    print(f"  Found {len(recipe_cards)} item cards in menu")
    for card in recipe_cards:
        try:
            name = get_text(card, './/span[contains(@class,"k10-recipe__name")]/text()')
            if not name:
                continue
            desc = get_text(card, './/div[contains(@class,"k10-recipe__description")]/text()')
            price = get_text(card, './/span[contains(@class,"k10-menu-item-card__price")]/text()')
            # Allergen icons/letters sometimes inside a container
            allergens = ' '.join([t.strip() for t in card.xpath('.//div[contains(@class,"allergen")]//text()') if t.strip()])
            if not allergens:
                allergens = ' '.join([t.strip() for t in card.xpath('.//div[contains(@class,"k10-menu-item-card__allergens")]//text()') if t.strip()])
            img = ''
            img_node = card.xpath('.//img[contains(@class,"k10-recipe__image")]/@src')
            if img_node:
                img = img_node[0]
            section = nearest_section(card)
            record = {
                'rest_name': REST_NAME,
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'menu_name': menu_name,
                'menu_section': section,
                'item_name': name,
                'item_description': desc,
            }
            if price:
                record['price'] = price
            if allergens:
                record['allergens'] = allergens
            if img:
                record['image_url'] = img
            results.append(record)
        except Exception as e:
            print(f"    Could not parse card: {e}")
            continue

    # BYO items (build-your-own components) if present
    byo_items = tree.xpath('//div[contains(@class,"k10-byo-item-card")]')
    for byo in byo_items:
        try:
            name = get_text(byo, './/span[contains(@class,"k10-byo-item__name")]/text()')
            if not name:
                continue
            price = get_text(byo, './/span[contains(@class,"k10-menu-item-card__price")]/text()')
            desc = get_text(byo, './/div[contains(@class,"k10-byo-item__description")]/text()')
            section = nearest_section(byo)
            record = {
                'rest_name': REST_NAME,
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'menu_name': menu_name,
                'menu_section': section,
                'item_name': name,
                'item_description': desc,
            }
            if price:
                record['price'] = price
            results.append(record)
        except Exception as e:
            print(f"    Could not parse BYO item: {e}")
            continue

    return results


def parse_jsonld_recursive(page_source: str) -> List[Dict]:
    """Extract all MenuItems from any JSON-LD Menu blocks in the page (recursive)."""
    tree = html.fromstring(page_source)
    scripts = tree.xpath('//script[@type="application/ld+json"]/text()')
    out: List[Dict] = []
    seen = set()

    def norm_price(p):
        if p is None or p == '':
            return ''
        s = str(p).strip()
        if s.startswith('£'):
            return s
        try:
            float(s)
            return f'£{s}'
        except Exception:
            return s

    def clean_desc(d):
        return (d or '').replace('<br/>',' ').replace('<br>',' ').replace('<br />',' ').strip()

    def add_item(menu_name, top_sec, sub_path, mi):
        if not isinstance(mi, dict) or mi.get('@type') != 'MenuItem':
            return
        name = (mi.get('name') or '').strip()
        if not name:
            return
        offers = mi.get('offers') or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        price = norm_price(offers.get('price')) if isinstance(offers, dict) else ''
        sub_section = ' > '.join(sub_path) if sub_path else ''
        key = (menu_name, top_sec, sub_section, name, price)
        if key in seen:
            return
        seen.add(key)
        rec = {
            'rest_name': REST_NAME,
            'collection_date': date.today().strftime('%b-%d-%Y'),
            'menu_name': menu_name,
            'menu_section': top_sec,
            'item_name': name,
            'item_description': clean_desc(mi.get('description') or ''),
        }
        if sub_section:
            rec['menu_sub_section'] = sub_section
        if price:
            rec['price'] = price
        nutr = mi.get('nutrition') or {}
        if isinstance(nutr, dict):
            for k,v in nutr.items():
                if v is None or v == '':
                    continue
                rec[f'nutrition_{k}'] = v
        out.append(rec)

    def walk_section(menu_name, section_obj, top=None, path=None):
        if not isinstance(section_obj, dict) or section_obj.get('@type') != 'MenuSection':
            return
        name = (section_obj.get('name') or '').strip()
        if not name:
            return
        if top is None:
            top = name
            path_for_children = []
        else:
            path_for_children = (path or []) + [name]
        mis = section_obj.get('hasMenuItem')
        if isinstance(mis, dict):
            add_item(menu_name, top, path_for_children, mis)
        elif isinstance(mis, list):
            for mi in mis:
                add_item(menu_name, top, path_for_children, mi)
        subs = section_obj.get('hasMenuSection')
        if isinstance(subs, dict):
            walk_section(menu_name, subs, top, path_for_children)
        elif isinstance(subs, list):
            for ss in subs:
                walk_section(menu_name, ss, top, path_for_children)

    def process_menu(m):
        menu_name = (m.get('name') or '').strip() or 'Menu'
        secs = m.get('hasMenuSection') or []
        if isinstance(secs, dict):
            walk_section(menu_name, secs)
        else:
            for s in secs:
                walk_section(menu_name, s)

    for raw in scripts:
        raw = (raw or '').strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            try:
                fixed = raw.replace('\n',' ').replace('\t',' ')
                data = json.loads(fixed)
            except Exception:
                continue
        candidates = []
        if isinstance(data, dict):
            if data.get('@type') == 'Menu' and data.get('hasMenuSection'):
                candidates.append(data)
            graph = data.get('@graph')
            if isinstance(graph, list):
                for g in graph:
                    if isinstance(g, dict) and g.get('@type') == 'Menu' and g.get('hasMenuSection'):
                        candidates.append(g)
        elif isinstance(data, list):
            for el in data:
                if isinstance(el, dict) and el.get('@type') == 'Menu' and el.get('hasMenuSection'):
                    candidates.append(el)
        for cm in candidates:
            process_menu(cm)
    return out


def save_outputs(records: List[Dict]):
    df = pd.DataFrame(records)
    df.to_csv(file_csv, index=False)
    with open(file_json, 'w') as f:
        import json as _json
        _json.dump(records, f, indent=2)
    with open(file_jsonl, 'w') as f:
        import json as _json
        for rec in records:
            f.write(_json.dumps(rec) + "\n")
    print(f"Scraped {len(records)} item(s)")
    print(f"Saved: {file_csv}")
    print(f"Saved: {file_json}")
    print(f"Saved: {file_jsonl}")


def dedupe_items(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for it in items:
        key = (
            it.get('item_name','').strip(),
            it.get('menu_section','').strip(),
            it.get('price','')
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def main():
    print(f"Landing URL: {LANDING_URL}")
    driver = setup_driver()
    items: List[Dict] = []
    try:
        driver.get(LANDING_URL)
        accept_cookies(driver)

        menu_pairs = wait_for_menu_pairs(driver)
        src = driver.page_source
        print(f"Found {len(menu_pairs)} menus")
        if not menu_pairs:
            items = parse_jsonld_recursive(src)
            print(f"Parsed {len(items)} JSON-LD items from landing page (fallback)")
        else:
            for menu_name, guid in menu_pairs:
                print(f'Rendering menu "{menu_name}" via mguid: {guid}')
                url = f"{LANDING_URL}?mguid={guid}"
                print(f"Render url: {url}")
                driver.get(url)
                time.sleep(1.0)
                page_src = driver.page_source
                items_html = extract_items_from_html(page_src, menu_name)
                if not items_html:  # fallback to JSON-LD if cards not yet visible or rendered differently
                    jsonld_items = parse_jsonld_recursive(page_src)
                    # Filter only those matching this menu_name (case-insensitive)
                    filtered = [r for r in jsonld_items if r.get('menu_name','').lower() == menu_name.lower()]
                    print(f"    Parsed {len(filtered)} JSON-LD items from menu '{menu_name}' (fallback)" )
                    items.extend(filtered)
                else:
                    print(f"    Parsed {len(items_html)} items from menu '{menu_name}'")
                    items.extend(items_html)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # Final dedupe after all collection passes
    items = dedupe_items(items)
    if not items:
        raise RuntimeError("Cafe Rouge scrape returned no items; existing outputs were not overwritten")
    save_outputs(items)


if __name__ == '__main__':
    main()
