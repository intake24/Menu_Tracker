from datetime import date
import os
import re
import time
import requests
import pandas as pd
from lxml import html

from define_collection_wave import folder
from helpers import create_folder, setup_driver

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

REST_NAME = "Bella Italia"
BASE_START = 'https://www.bellaitalia.co.uk/restaurants/cambridge/leisure-park/menu'
TK_BASE = 'https://menus.tenkites.com/thebigtg/mobilemenus03'

# Outputs
path_out = create_folder("81_BellaItalian", folder)
file_json = os.path.join(path_out, "bella_italia_items.json")
file_csv = os.path.join(path_out, "bella_italia_items.csv")


def get_text(node, xpath_expr: str) -> str:
    try:
        res = node.xpath(xpath_expr)
        if not res:
            return ''
        if isinstance(res, list):
            val = res[0]
        else:
            val = res
        if hasattr(val, 'text_content'):
            return val.text_content().strip()
        return str(val).strip()
    except Exception:
        return ''


def parse_menu_page(page_tree, menu_name: str) -> list[dict]:
    """Parse a Ten Kites mobile menu page (mobilemenus03) into item dicts.
    Handles generic course/recipe widgets and BYO (build-your-own) variants.
    Extracts: item_name, item_description, menu_section, optional price/calories, plus any nutrition table rows.
    """
    items_all: list[dict] = []
    # Prefer sections that contain a visible course name, fallback to nested sections
    menu_sections = page_tree.xpath(
        '//section[.//div[contains(@class,"k10-w-course__name") or contains(@class,"k10-course__name")]]'
    )
    print(f"Menu '{menu_name}': found {len(menu_sections)} section(s)")

    # Track seen keys to avoid duplicates within the rendered page
    seen_keys: set[tuple] = set()

    for menu_section in menu_sections:
        menu_section_name = (
            get_text(menu_section, './/div[contains(@class,"k10-w-course__name-text")]/text()')
            or get_text(menu_section, './/div[contains(@class,"k10-course__name")]/text()')
        )
        # 1) Generic recipe items (most common in Ten Kites)
        recipe_nodes = menu_section.xpath(
            './/div[contains(@class,"k10-w-recipe") and contains(@class,"k10-recipe_menu-item")]| .//div[contains(@class,"k10-recipe") and contains(@class,"k10-recipe_menu-item")]'
        )
        section_added = 0
        print(f"  Section: '{menu_section_name or '(unnamed)'}' -> recipes: {len(recipe_nodes)}")
        for r in recipe_nodes:
            item_name = get_text(r, './/span[contains(@class, "k10-w-recipe__name")]/text() | .//span[contains(@class, "k10-recipe__name")]/text()')
            item_desc = get_text(r, './/span[contains(@class, "k10-w-recipe__desc")]/text() | .//span[contains(@class, "k10-recipe__desc")]/text()')
            price = get_text(r, './/span[contains(@class, "k10-w-recipe__price")]/text() | .//span[contains(@class, "k10-recipe__price")]/text()')
            calories = r.get('data-calories') or ''
            recipe_guid = (r.get('data-guid') or r.get('data-recipe-guid') or r.get('data-recipe-id') or '').strip()

            if item_name:
                # Build stable dedupe key: prefer recipe id; fallback to (name, section)
                sec_name = menu_section_name or ''
                dedupe_key = (recipe_guid.lower(),) if recipe_guid else (item_name.strip(), sec_name.strip())
                if dedupe_key in seen_keys:
                    continue
                item_dict: dict = {
                    'rest_name': REST_NAME,
                    'collection_date': date.today().strftime('%b-%d-%Y'),
                    'item_name': item_name,
                    'item_description': item_desc,
                    'menu_section': f"{menu_name}, {menu_section_name}" if menu_section_name else menu_name,
                }
                if price:
                    item_dict['price'] = price
                if calories:
                    item_dict['calories'] = calories
                if recipe_guid:
                    item_dict['recipe_id'] = recipe_guid

                # Dietary/allergen labels (e.g. GF, VG, V) embedded in the item's
                # own modal markup -- no separate PDF needed, they're already here.
                label_nodes = r.xpath('.//span[contains(@class, "k10-recipe-modal__label")]')
                labels = [n.text_content().strip() for n in label_nodes if n.text_content().strip()]
                if labels:
                    item_dict['allergens'] = ', '.join(dict.fromkeys(labels))

                # Inline nutrition table rows if present under this recipe node
                nutrition_rows = r.xpath('.//table//tr')
                for row in nutrition_rows:
                    nkey = get_text(row, './td[1]/text()')
                    nval = get_text(row, './td[2]/text()')
                    if nkey:
                        item_dict[nkey] = nval

                items_all.append(item_dict)
                section_added += 1
                seen_keys.add(dedupe_key)

        # 2) BYO items (e.g., wines with multiple variants)
        grid_items = menu_section.xpath('.//div[contains(@class, "k10-l-grid__item")]')
        for item in grid_items:
            item_vars = item.xpath('.//div[contains(@class, "k10-byo__item") and contains(@class, "k10-byo-item")]')
            if not item_vars:
                continue
            item_description = get_text(item, './/div[@class="k10-byo-item__desc"]/text()')
            has_header = bool(item.xpath('.//div[contains(@class, "k10-byo__header")]'))

            wine_name = ''
            wine_description = ''
            if has_header:
                wine_name = get_text(item, './/div[contains(@class, "k10-byo__header")]//span[@class="k10-byo__name"]/text()')
                wine_description = get_text(item, './/div[contains(@class, "k10-byo__header")]//div[@class="k10-byo__desc"]/text()')

            for item_var in item_vars:
                if has_header:
                    item_name = (wine_name + ' ' + get_text(item_var, './/span[@class="k10-byo-item__name"]/text()')).strip()
                    item_desc = wine_description
                else:
                    item_name = get_text(item_var, './/span[@class="k10-byo-item__name"]/text()')
                    item_desc = item_description

                if not item_name:
                    continue

                # BYO variants typically lack stable ids; dedupe by (name, section)
                sec_name = menu_section_name or ''
                dedupe_key = (item_name.strip(), sec_name.strip())
                if dedupe_key in seen_keys:
                    continue

                item_dict = {
                    'rest_name': REST_NAME,
                    'collection_date': date.today().strftime('%b-%d-%Y'),
                    'item_name': item_name,
                    'item_description': item_desc,
                    'menu_section': f"{menu_name}, {menu_section_name}" if menu_section_name else menu_name,
                }
                # Nutrition rows: two-column key/value
                nutrition_rows = item_var.xpath('.//table//tr')
                for row in nutrition_rows:
                    nkey = get_text(row, './td[1]/text()')
                    nval = get_text(row, './td[2]/text()')
                    if nkey:
                        item_dict[nkey] = nval
                items_all.append(item_dict)
                section_added += 1
                seen_keys.add(dedupe_key)

        print(f"  Section: '{menu_section_name or '(unnamed)'}' -> added {section_added} item(s)")

    return items_all


def extract_menu_guids(tree) -> list[tuple[str, str]]:
    """Extract (menu_name, guid) tuples from the Ten Kites selector options."""
    pairs: list[tuple[str, str]] = []
    options = tree.xpath('//div[contains(@class, "k10-menu-selector__option")]')
    guid_re = re.compile(r'[0-9a-fA-F\-]{36}')
    seen: set[str] = set()
    for i, opt in enumerate(options):
        name = get_text(opt, './/span/text()')
        guid = ''
        # common data attrs on Ten Kites
        for attr in ['data-guid', 'data-mguid', 'data-id', 'data-value','data-menu-identifier']:
            val = opt.get(attr)
            if val and guid_re.fullmatch(val.strip()):
                guid = val.strip()
                break
        if not guid:
            # fallback: search in HTML snippet
            snip = html.tostring(opt, encoding='unicode')
            m = guid_re.search(snip)
            if m:
                guid = m.group(0)
        if name and guid and guid not in seen:
            seen.add(guid)
            pairs.append((name.strip(), guid))
    return pairs


def render_tk_menu(driver, guid: str) -> str:
    """Load a Ten Kites mobile menu page with Selenium and return rendered HTML."""
    url = f"{TK_BASE}?mguid={guid}"
    print(f"Render TK url: {url}")
    driver.get(url)
    # Wait for any course/recipe elements to appear
    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((
            By.XPATH,
            "//section|//div[contains(@class,'k10-w-recipe') or contains(@class,'k10-recipe') or contains(@class,'k10-course')]"
        )))
    except Exception:
        pass

    # Attempt to reveal dynamic content: scroll and click expanders if present
    last_height = 0
    for _ in range(6):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.6)
        new_height = driver.execute_script("return document.body.scrollHeight;")
        if new_height == last_height:
            break
        last_height = new_height

    # Try to click any common expand/collapse toggles
    try:
        # toggles = driver.find_elements(By.XPATH, "//button[contains(translate(., 'SHOWMOREEXPAND', 'showmoreexpand'),'show') or contains(., '+')] | //div[contains(@class,'k10-accordion') or contains(@class,'k10-expand')]//button")
        toggles = driver.find_elements(By.XPATH, "//div[contains(@class, 'k10-course__name-container')]")
        for t in toggles:
            try:
                driver.execute_script("arguments[0].click();", t)
                time.sleep(0.1)
            except Exception:
                continue
    except Exception:
        pass

    return driver.page_source


def main():
    items_all: list[dict] = []

    # 1) Fetch landing page and try to collect menu options
    print(f"Landing URL: {BASE_START}")
    landing_html = requests.get(BASE_START).text
    print(f"Fetched landing page, length {len(landing_html)} chars")
    landing_tree = html.fromstring(landing_html)

    menu_pairs = extract_menu_guids(landing_tree)
    print(f"Found {len(menu_pairs)} menu option(s) from selector")

    # Dedupe menus by GUID to avoid rendering same menu twice
    if menu_pairs:
        seen_guids: set[str] = set()
        deduped: list[tuple[str, str]] = []
        for name, guid in menu_pairs:
            if guid not in seen_guids:
                seen_guids.add(guid)
                deduped.append((name, guid))
        if len(deduped) != len(menu_pairs):
            print(f"Deduped menu options: {len(menu_pairs)} -> {len(deduped)}")
        menu_pairs = deduped

    # 2) If none, try direct TK base once to discover options
    if not menu_pairs:
        print('No explicit menus found on landing page; trying direct Ten Kites base URL...')
        tk_html = requests.get(TK_BASE).text
        tk_tree = html.fromstring(tk_html)
        menu_pairs = extract_menu_guids(tk_tree)
        print(f"Found {len(menu_pairs)} menu option(s) on TK base")

    # 3) If still none, render TK base with Selenium and parse single visible content
    driver = setup_driver()
    try:
        if not menu_pairs:
            print('No explicit menus found on Ten Kites base; rendering visible content as a single menu...')
            html_rendered = render_tk_menu(driver, guid='') if False else ''  # placeholder; no guid for base
            # Fallback: load TK_BASE without guid
            driver.get(TK_BASE)
            time.sleep(1)
            tk_src = driver.page_source
            tk_tree2 = html.fromstring(tk_src)
            parsed = parse_menu_page(tk_tree2, menu_name='Menu')
            items_all.extend(parsed)
            print(f"Parsed fallback menu -> {len(parsed)} item(s)")
        else:
            # 4) Iterate menus via mguid and render with Selenium
            for menu_name, guid in menu_pairs:
                print(f'Rendering menu "{menu_name}" via mguid: {guid}')
                page_src = render_tk_menu(driver, guid)
                tk_tree = html.fromstring(page_src)
                parsed = parse_menu_page(tk_tree, menu_name=menu_name)
                items_all.extend(parsed)
                print(f'Added {len(parsed)} item(s) for menu "{menu_name}"')
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # Save outputs
    items_df = pd.DataFrame(items_all)
    items_df.to_csv(file_csv, index=False)
    with open(file_json, 'w') as f:
        import json
        json.dump(items_all, f, indent=2)
    print(f'Scraped total {len(items_all)} item(s).')
    print(f'Saved: {file_csv}')
    print(f'Saved: {file_json}')


if __name__ == '__main__':
    main()
