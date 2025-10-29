import json
from datetime import date
from time import sleep

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from define_collection_wave import folder
from helpers import create_folder, setup_driver, clean_text, try_click_accept_cookies, get_visible_text

path_out = create_folder('29_AllBarOne', folder)
file_json = path_out + '/allbarone_nutrition.json'
file_csv = path_out + '/allbarone_nutrition.csv'
REST_NAME = "All Bar One"

START_URL = 'https://www.allbarone.co.uk/food-and-drink'

def _parse_nutrition_table_from(container, driver) -> dict:
    """Parse a two-column nutrition table within the given container. Returns label->value mapping."""
    data = {}
    # Try common nutrition table candidates near the container
    table_selectors = [
        ".//table[contains(@class,'Nutrition') or contains(@class,'nutrition') or contains(@class,'Nutri')]",
        ".//table",
    ]
    table = None
    # If the container itself is a table, parse it directly
    try:
        if hasattr(container, 'tag_name') and (container.tag_name or '').lower() == 'table':
            table = container
    except Exception:
        pass
    if table is not None:
        try:
            print("    - Found nutrition table directly from container tag")
        except Exception:
            pass
    for xp in table_selectors:
        try:
            print(f"    - Searching for table with XPath: {xp}")
            tbls = container.find_elements(By.XPATH, xp)
            if tbls:
                table = tbls[0]
                print("    - Nutrition table found via XPath selector")
                break
        except Exception:
            continue
    if not table:
        try:
            print("    - No nutrition table found in container")
        except Exception:
            pass
        return data
    try:
        rows = table.find_elements(By.XPATH, ".//tr")
        print(f"    - Parsing nutrition table rows: {len(rows)}")
        for row in rows:
            try:
                # Prefer th/td pair, else td/td
                cells = row.find_elements(By.XPATH, ".//th|.//td")
                if len(cells) < 2:
                    continue
                for cell in cells:
                    raw_cell_text = clean_text(get_visible_text(cell, driver))
                    label = raw_cell_text.split(':')[0].strip().lower()
                    value = raw_cell_text.split(':')[1].strip().lower() if ':' in raw_cell_text else ''
                    if label:
                        data[label] = value
            except Exception:
                continue
    except Exception:
        pass
    try:
        print(f"    - Parsed nutrition labels: {list(data.keys())}")
    except Exception:
        pass
    return data


def _extract_nut_info_from_card(card, driver) -> dict:
    """Within a food card, expand Allergens and Nutritional Information sections and capture data.

    - Click div.AllergenInfo__expandable then scrape allergen text within the card
    - Click div.NutritionalInfo__expandable then parse table.NutritionalInfo__table.NutritionalInfo__table--small
    """
    info = {
        'allergens': None,
        'kcal': None,
        'kj': None,
        'fat': None,
        'satfat': None,
        'carb': None,
        'sugar': None,
        'protein': None,
        'salt': None,
        '__raw_nutrition__': {},
    }

    # Ensure card is visible
    try:
        print("  - Scrolling card into view")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
        sleep(0.2)
    except Exception:
        pass

    # Capture expected title from the card (to validate modal content)
    expected_title = None
    try:
        expected_title = _extract_food_name_from_card(card, driver)
    except Exception:
        expected_title = None

    # Click on the card to open details (often a modal)
    try:
        # print heading of the current card 
        print(f"  - Current card heading: {expected_title}")
        print("  - Clicking on card to open details (JS)")
        driver.execute_script("arguments[0].click();", card)
        sleep(0.4)
    except Exception:
        pass

    # Locate the correct, visible modal for this card by matching its heading
    modal_card = None
    print("  - Waiting for visible modal to match current card heading…")
    for attempt in range(24):  # ~6 seconds total
        try:
            candidates = driver.find_elements(By.XPATH, "//*[@role='dialog' or @aria-modal='true' or contains(@class,'Modal') or contains(@class,'modal')]")
        except Exception:
            candidates = []
        matched = None
        top_visible = None
        top_z = -1
        for cand in candidates:
            try:
                if not cand.is_displayed():
                    continue
                # pick topmost visible as fallback
                try:
                    z = driver.execute_script("return parseInt(window.getComputedStyle(arguments[0]).zIndex) || 0;", cand)
                except Exception:
                    z = 0
                if z >= top_z:
                    top_z, top_visible = z, cand
                # check heading
                try:
                    heading = cand.find_element(By.XPATH, ".//h1 | .//h2 | .//h3 | .//h4")
                    htxt = (heading.text or heading.get_attribute('innerText') or '').strip()
                except Exception:
                    htxt = ''
                if expected_title and htxt and expected_title.lower() in htxt.lower():
                    matched = cand
                    print(f"  - Modal heading matched: {htxt}")
                    break
            except Exception:
                continue
        if matched is not None:
            modal_card = matched
            break
        # fallback: if no match, but a visible modal exists and no expected_title, use it
        if not expected_title and top_visible is not None:
            modal_card = top_visible
            try:
                heading = modal_card.find_element(By.XPATH, ".//h1 | .//h2 | .//h3 | .//h4")
                print(f"  - Modal detected (no expected title). Heading: {(heading.text or '').strip()}")
            except Exception:
                print("  - Modal detected (no expected title). Heading: <none>")
            break
        sleep(0.25)
    if modal_card is None:
        print("  - No matching visible modal found; using card element for extraction")
        modal_card = card

    # Expand Allergens section within the card
    try:
        allergen_toggle = None
        try:
            allergen_toggle = modal_card.find_element(By.CSS_SELECTOR, "div.AllergenInfo__expandable")
        except Exception:
            # Fallback XPath
            try:
                allergen_toggle = modal_card.find_element(By.XPATH, ".//div[contains(@class,'AllergenInfo__expandable')]")
            except Exception:
                allergen_toggle = None
        print(f"  - Allergen toggle present: {bool(allergen_toggle)}")
        if allergen_toggle:
            try:
                print("  - Clicking allergen toggle (JS)")
                driver.execute_script("arguments[0].click();", allergen_toggle)
            except Exception:
                try:
                    print("  - Clicking allergen toggle (native)")
                    allergen_toggle.click()
                except Exception:
                    pass
            sleep(0.4)
            # After expand, try to capture allergen text from typical containers within the card
            # Accumulate allergen labels across all candidate containers, de-duplicated
            collected_allergens = []
            seen_allergens = set()
            candidates = [
                ".//div[contains(@class,'AllergenInfo__allergens__pills__wrapper')]",
                # ".//*[contains(@class,'AllergenInfo__content')]",
                # ".//*[contains(@class,'AllergenInfo__list')]",
                # ".//*[contains(translate(@class, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'allergen') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'allergen')]",
            ]
            for xp in candidates:
                try:
                    print(f"  - Searching allergen content with XPath: {xp}")
                    els = allergen_toggle.find_elements(By.XPATH, xp)
                    print(f"    - Found {len(els)} allergen content elements")
                    for el in els:
                        # Prefer collecting pill-like descendants to build a concise list
                        try:
                            pill_nodes = el.find_elements(
                                By.XPATH,
                                ".//*[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'pill') or self::li or self::span]"
                            )
                            print(f"    - Found {len(pill_nodes)} allergen pill nodes")
                        except Exception:
                            pill_nodes = []
                        texts = []
                        for pn in pill_nodes:
                            t = clean_text(get_visible_text(pn, driver))
                            if t and t not in ('Contains', 'Allergens', 'May contain'):
                                texts.append(t)
                        # Deduplicate while preserving order
                        if texts:
                            dedup = list(dict.fromkeys(texts))
                            for token in dedup:
                                if token not in seen_allergens:
                                    seen_allergens.add(token)
                                    collected_allergens.append(token)
                    
                    # if info['allergens']:
                    #     break
                except Exception:
                    continue
            if collected_allergens:
                txt_joined = ", ".join(collected_allergens)
                if len(txt_joined) > 3:
                    info['allergens'] = txt_joined
                    print(f"  - Allergen pills captured: {txt_joined}")
    except Exception:
        pass

    # Expand Nutritional Information and parse the nutrition table
    try:
        nut_toggle = None
        try:
            nut_toggle = modal_card.find_element(By.CSS_SELECTOR, "div.NutritionalInfo__expandable")
        except Exception:
            try:
                nut_toggle = modal_card.find_element(By.XPATH, ".//div[contains(@class,'NutritionalInfo__expandable')]")
            except Exception:
                nut_toggle = None
        print(f"  - Nutritional toggle present: {bool(nut_toggle)}")
        if nut_toggle:
            try:
                print("  - Clicking nutrition toggle (JS)")
                driver.execute_script("arguments[0].click();", nut_toggle)
            except Exception:
                try:
                    print("  - Clicking nutrition toggle (native)")
                    nut_toggle.click()
                except Exception:
                    pass
            sleep(0.3)
        # Parse nutrition table within the card
        raw_map = {}
        # Prefer the small NutritionalInfo table first
        try:
            tbl = nut_toggle.find_element(By.CSS_SELECTOR, "table.NutritionalInfo__table.NutritionalInfo__table--small")
            print("  - Found small nutrition table via CSS")
            raw_map = _parse_nutrition_table_from(tbl, driver)
        except Exception:
            # Fallback: any NutritionalInfo table under the card
            try:
                tbl = nut_toggle.find_element(By.XPATH, ".//table[contains(@class,'NutritionalInfo__table')]")
                print("  - Found nutrition table via XPath fallback")
                raw_map = _parse_nutrition_table_from(tbl, driver)
            except Exception:
                print("  - Nutrition table not found, skipping...")

        info['__raw_nutrition__'] = raw_map or {}
        if raw_map:
            def pick(keys):
                for k in keys:
                    for rk in raw_map.keys():
                        if k.lower() in rk.lower():
                            return raw_map[rk]
                return None
            info['kcal'] = info['kcal'] or pick(['kcal', 'calorie'])
            info['kj'] = info['kj'] or pick(['kj'])
            info['fat'] = info['fat'] or pick(['fat'])
            info['satfat'] = info['satfat'] or pick(['saturates', 'saturated'])
            info['carb'] = info['carb'] or pick(['carb', 'carbohydrate'])
            info['sugar'] = info['sugar'] or pick(['sugar'])
            info['protein'] = info['protein'] or pick(['protein'])
            info['salt'] = info['salt'] or pick(['salt', 'sodium'])
            print("  - Nutrition fields mapped:", {k: v for k, v in info.items() if k in ['kcal','kj','fat','satfat','carb','sugar','protein','salt'] and v})
    except Exception:
        pass

    # Best-effort: close the modal to ensure next loop opens fresh content
    try:
        print("  - Attempting to close modal/menu-item card")
        close_el = card.find_element(By.XPATH, "//*[contains(@class,'Modal__box')]")
        if close_el:
            print("  - Close element found")
        else:
            print("  - Close element not found")
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", close_el)
        except Exception:
            pass
        try:
            driver.execute_script("arguments[0].click();", close_el)
            print("  - Closed modal (JS)")
        except Exception:
            try:
                close_el.click()
                print("  - Closed modal (native)") 
            except Exception:
                print("  - Failed to close modal")
                return
        # check whether modal is closed
        try:
            print("  - Checking if modal is closed")
            WebDriverWait(driver, 0.5).until(
                EC.invisibility_of_element_located(
                    (By.XPATH, "//*[contains(@class,'Modal') or contains(@class,'modal-menu-item')]")
                )
            )
            print("  - Modal may still be open; proceeding anyway")
        except Exception:
            print("  - Modal closed confirmed")
        sleep(0.2)
    except Exception as e:
        print(f"  - Failed to close modal: {e}")
        pass

    return info

def _extract_food_name_from_card(card, driver) -> str:
    """Try multiple selectors and fallbacks to extract a food name from a card."""
    candidate_xpaths = [
        ".//h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6",
        # ".//*[contains(translate(@class,'TITLE','title'),'title')]",
        # ".//*[contains(translate(@class,'NAME','name'),'name')]",
    ]
    for xp in candidate_xpaths:
        try:
            for el in card.find_elements(By.XPATH, xp):
                txt = clean_text(get_visible_text(el, driver))
                if txt:
                    try:
                        print(f"  - Found food name: {txt}")
                    except Exception:
                        pass
                    return txt
        except Exception:
            continue

def crawl_nutrition():
    driver = setup_driver()
    try_click_accept_cookies(driver)
    results = []

    def wait_for_menu_grid():
        WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, "//*[@class='image parbase section']"))
        )

    def find_food_cards(timeout, menu_url):
        """Try multiple selectors to find food cards on a menu page."""
        print(f"Navigating to menu URL: {menu_url}")
        driver.get(menu_url)
        selectors = [
            # (By.CSS_SELECTOR, "div.MenuItem__wrapper"),
            (By.XPATH, "//div[contains(@class,'MenuItem__wrapper')]") ,
            # (By.XPATH, "//div[contains(@class,'menu-item') or contains(@class,'MenuItem')]") ,
            # (By.CSS_SELECTOR, "[data-component='menu-item']"),
        ]
        for by, sel in selectors:
            try:
                print(f"  - Waiting for food cards with selector: {sel}")
                els = WebDriverWait(driver, timeout).until(
                    EC.presence_of_all_elements_located((by, sel))
                )
                if els:
                    print(f"  - Found {len(els)} food cards")
                    return els
            except TimeoutException:
                print("  - Selector timed out; trying next")
                continue
        return []

    try:
        driver.get(START_URL)
        print('Page URL:', driver.current_url)
        print('Waiting for menu items to load...')
        WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, "//*[@class='image parbase section']") )
        )
        sleep(0.5)
        print('Menu items loaded.')

        menu_els = driver.find_elements(By.XPATH, "//*[@class='image parbase section']//a")
        food_menus_urls = [el.get_attribute("href") for el in menu_els]
        print(f'Found {len(food_menus_urls)} menu items')

        for idx, menu_url in enumerate(food_menus_urls):
            # # Skip all except the 5th menu for testing
            # if idx != 4:
            #     continue
            try:
                # Find food cards, with a fallback to a generic 'menu' link
                foods = find_food_cards(timeout=8, menu_url=menu_url)
                print(f"Found {len(foods)} foods in menu {idx+1}, url: {menu_url}")
                for f_idx, food in enumerate(foods):
                    try:
                        print(f"Processing food card {f_idx+1}/{len(foods)}")
                        # 1) Try to read directly from the food card
                        food_name = _extract_food_name_from_card(food, driver)

                        # 2) Build record by extracting allergens/nutrition
                        print("  -> Extracting allergens and nutrition...")
                        nut_info = _extract_nut_info_from_card(food, driver)
                        record = {
                            'collection_date': date.today().strftime('%b-%d-%Y'),
                            'rest_name': REST_NAME,
                            'menu_section': menu_url.rstrip('/').split('/')[-1] if '/' in menu_url else 'Unknown',
                            'item_name': food_name or '',
                            'allergens': nut_info.get('allergens'),
                            'kj': nut_info.get('kj'),
                            'kcal': nut_info.get('kcal'),
                            'fat': nut_info.get('fat'),
                            'satfat': nut_info.get('satfat'),
                            'carb': nut_info.get('carb'),
                            'sugar': nut_info.get('sugar'),
                            'protein': nut_info.get('protein'),
                            'salt': nut_info.get('salt'),
                        }
                        results.append(record)
                        print(f"  [{f_idx+1}/{len(foods)}] Food: {food_name or '<empty>'} -> captured fields: "
                              f"{ {k:v for k,v in record.items() if k in ['allergens','kj','kcal','fat','satfat','carb','sugar','protein','salt'] and v} }")
                    except Exception as e:
                        print(f"  Error processing food item: {e}")
                        continue
                
                # Return to the main grid of menu tiles for next menu url
                try:
                    driver.back()
                    wait_for_menu_grid()
                    sleep(0.2)
                except Exception:
                    pass
            except Exception as e:
                print(f"Error processing item {idx+1}: {e}, back and waiting for menu grid")
                try:
                    driver.back()
                    wait_for_menu_grid()
                except Exception:
                    pass
                continue

        # Save outputs
        with open(file_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Scraped {len(results)} items. Data saved to {file_json}")
        if results:
            pd.DataFrame(results).to_csv(file_csv, index=False)
            print(f"Data also saved to CSV: {file_csv}")
    except TimeoutException:
        print('Timed out waiting for menu items.')
    except Exception as e:
        print(f'Error during scraping: {e}')
    finally:
        driver.quit()


if __name__ == '__main__':
    crawl_nutrition()

