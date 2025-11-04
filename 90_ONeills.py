import json
import logging
from datetime import date
from time import sleep

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from define_collection_wave import folder
from helpers import create_folder, setup_driver, clean_text, try_click_accept_cookies, get_visible_text, set_driver_timeouts, safe_get

path_out = create_folder('90_ONeills', folder)
file_json = path_out + '/oneills_nutrition.json'
file_csv = path_out + '/oneills_nutrition.csv'
REST_NAME = "ONeills"

START_URL = 'https://www.oneills.co.uk/food-and-drink#/'
menu_urls_xpath_expr = "//*[@class='image parbase section']"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.formatter = logging.Formatter('%(message)s')

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
            logger.debug("Found nutrition table directly from container tag")
        except Exception:
            pass
    for xp in table_selectors:
        try:
            logger.debug(f"Searching for table with XPath: {xp}")
            tbls = container.find_elements(By.XPATH, xp)
            if tbls:
                table = tbls[0]
                logger.debug("Nutrition table found via XPath selector")
                break
        except Exception:
            continue
    if not table:
        try:
            logger.debug("No nutrition table found in container")
        except Exception:
            pass
        return data
    try:
        rows = table.find_elements(By.XPATH, ".//tr")
        logger.debug(f"Parsing nutrition table rows: {len(rows)}")
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
        logger.debug(f"Parsed nutrition labels: {list(data.keys())}")
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
        logger.debug("Scrolling card into view")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", card)
        WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located(card )
        )
    except Exception:
        pass

    # Click on the card to open details (often a modal)
    try:
        # print heading of the current card 
        logger.debug("Clicking on card to open details (JS)")
        driver.execute_script("arguments[0].click();", card)
        sleep(0.2)
    except Exception:
        pass

    modal_card = None
    logger.debug("Look for visible modals…")
    candidates = driver.find_elements(By.XPATH, "//div[contains(@class,'Modal__modal Modal-menu-item')]")
    logger.debug(f"Found {len(candidates)} candidate modals")
    modal_card = candidates[0]
    heading = modal_card.find_element(By.XPATH, ".//h1 | .//h2 | .//h3 | .//h4")
    htxt = (heading.text or heading.get_attribute('innerText') or '').strip()
    logger.debug(f"Modal heading: {htxt}")

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
        logger.debug(f"Allergen toggle present: {bool(allergen_toggle)}")
        if allergen_toggle:
            try:
                logger.debug("Clicking allergen toggle (JS)")
                driver.execute_script("arguments[0].click();", allergen_toggle)
            except Exception:
                try:
                    logger.debug("Clicking allergen toggle (native)")
                    allergen_toggle.click()
                except Exception:
                    pass
            # sleep(0.2)
            # After expand, capture allergen pills and de-duplicate while preserving order
            collected_allergens = []
            seen_allergens = set()
            try:
                xp = ".//div[contains(@class,'AllergenInfo__allergens__pills__wrapper')]"
                logger.debug(f"Searching allergen content with XPath: {xp}")
                # Wait for elements by locator (presence_of_all_elements_located expects a locator tuple)
                WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.XPATH, xp))
                )
                els = allergen_toggle.find_elements(By.XPATH, xp)
                logger.debug(f"Found {len(els)} allergen content elements")
                
                for el in els:
                    pill_nodes = el.find_elements(
                        By.XPATH,
                        ".//*[contains(translate(@class,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'pill') or self::li or self::span]"
                    )
                    logger.debug(f"Found {len(pill_nodes)} allergen pill nodes")
                    for pn in pill_nodes:
                        t = clean_text(get_visible_text(pn, driver))
                        if t and t not in ('Contains', 'Allergens', 'May contain') and t not in seen_allergens:
                            seen_allergens.add(t)
                            collected_allergens.append(t)
            except Exception as e:
                logger.warning(f"Exceptions when finding allergen info {e}")
                pass
            if collected_allergens:
                txt_joined = ", ".join(collected_allergens)
                if len(txt_joined) > 3:
                    info['allergens'] = txt_joined
                    logger.debug(f"Allergen pills captured: {txt_joined}")
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
        logger.debug(f"Nutritional toggle present: {bool(nut_toggle)}")
        if nut_toggle:
            try:
                logger.debug("Clicking nutrition toggle (JS)")
                driver.execute_script("arguments[0].click();", nut_toggle)
            except Exception:
                try:
                    logger.debug("Clicking nutrition toggle (native)")
                    nut_toggle.click()
                except Exception:
                    pass
            sleep(0.3)
        # Parse nutrition table within the card
        raw_map = {}
        # Prefer the small NutritionalInfo table first
        try:
            tbl = nut_toggle.find_element(By.CSS_SELECTOR, "table.NutritionalInfo__table.NutritionalInfo__table--small")
            logger.debug("Found small nutrition table via CSS")
            raw_map = _parse_nutrition_table_from(tbl, driver)
        except Exception:
            # Fallback: any NutritionalInfo table under the card
            try:
                tbl = nut_toggle.find_element(By.XPATH, ".//table[contains(@class,'NutritionalInfo__table')]")
                logger.debug("Found nutrition table via XPath fallback")
                raw_map = _parse_nutrition_table_from(tbl, driver)
            except Exception:
                logger.info("Nutrition table not found, skipping…")

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
            logger.debug("Nutrition fields mapped: %s", {k: v for k, v in info.items() if k in ['kcal','kj','fat','satfat','carb','sugar','protein','salt'] and v})
    except Exception:
        pass

    # Best-effort: close the modal to ensure next loop opens fresh content
    try:
        logger.debug("Attempting to close modal/menu-item card")
        close_el = card.find_element(By.XPATH, "//*[contains(@class,'Modal__box')]")
        if close_el:
            logger.debug("Close element found")
        else:
            logger.debug("Close element not found")
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", close_el)
        except Exception:
            pass
        try:
            driver.execute_script("arguments[0].click();", close_el)
            logger.debug("Closed modal (JS)")
        except Exception:
            try:
                close_el.click()
                logger.debug("Closed modal (native)") 
            except Exception:
                logger.warning("Failed to close modal")
                return
        # check whether modal is closed
        try:
            logger.debug("Checking if modal is closed")
            WebDriverWait(driver, 0.5).until(
                EC.invisibility_of_element_located(
                    (By.XPATH, "//*[contains(@class,'Modal') or contains(@class,'modal-menu-item')]")
                )
            )
            logger.debug("Modal may still be open; proceeding anyway")
        except Exception:
            logger.debug("Modal closed confirmed")
        sleep(0.2)
    except Exception as e:
        logger.warning(f"Failed to close modal: {e}")
        pass
    
    # Clean-up DOM: remove any lingering modal element modal_card
    try:
        if modal_card:
            driver.execute_script("arguments[0].remove();", modal_card)
            logger.debug("Removed lingering modal element")
    except Exception as e:
        logger.debug(f"Failed to remove lingering modal element: {e}")
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
                        logger.debug(f"Found food name: {txt}")
                    except Exception:
                        pass
                    return txt
        except Exception:
            continue

def crawl_nutrition():
    menu_driver = setup_driver()
    set_driver_timeouts(menu_driver)
    try_click_accept_cookies(menu_driver)
    results = []

    try:
        menu_driver.get(START_URL)
        logger.info('Page URL: %s', menu_driver.current_url)
        logger.info('Waiting for menu items to load…')
        WebDriverWait(menu_driver, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, menu_urls_xpath_expr))
        )
        logger.info('Menu items loaded.')

        menu_els = menu_driver.find_elements(By.XPATH, menu_urls_xpath_expr + "//a")
        food_menus_urls = [el.get_attribute("href") for el in menu_els]
        logger.info('Found %d menu items', len(food_menus_urls))

        for idx, menu_url in enumerate(food_menus_urls):
            # Skip all except the 5th menu for testing
            # if idx not in [3,4]:
            #     continue
            try:
                # Navigate to menu and find food cards (inlined from former find_food_cards)
                logger.info("Navigating to menu URL: %s", menu_url)
                menu_driver = safe_get(menu_driver, menu_url, wait_timeout=8)
                by, sel = (By.XPATH, "//div[contains(@class,'MenuItem__wrapper')]")
                try:
                    logger.debug("Waiting for food cards with selector: %s", sel)
                    food_cards = WebDriverWait(menu_driver, 8).until(
                        EC.presence_of_all_elements_located((by, sel))
                    )
                    logger.info("Found %d food cards", len(food_cards))
                except TimeoutException:
                    logger.warning("Selector timed out")
                    food_cards = []
                logger.info("Found %d foods in menu %d, url: %s", len(food_cards), idx+1, menu_url)
                for f_idx, card in enumerate(food_cards):
                    # if (f_idx != 13):  # For debugging specific item
                    #     continue
                    try:
                        logger.debug("Processing food card %d/%d", f_idx+1, len(food_cards))
                        # 1) Try to read directly from the food card
                        food_name = _extract_food_name_from_card(card, menu_driver)

                        # 2) Build record by extracting allergens/nutrition
                        logger.debug("Extracting allergens and nutrition…")
                        nut_info = _extract_nut_info_from_card(card, menu_driver)
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
                        logger.debug("[%d/%d] Food: %s -> captured fields: %s",
                                     f_idx+1, len(food_cards), food_name or '<empty>',
                                     {k:v for k,v in record.items() if k in ['allergens','kj','kcal','fat','satfat','carb','sugar','protein','salt'] and v})
                    except Exception as e:
                        logger.warning("Error processing food item: %s", e)
                        continue
            except Exception as e:
                logger.warning("Error processing item %d: %s, proceeding to next menu", idx+1, e)
                continue

        # Save outputs
        with open(file_json, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info("Scraped %d items. Data saved to %s", len(results), file_json)
        if results:
            pd.DataFrame(results).to_csv(file_csv, index=False)
            logger.info("Data also saved to CSV: %s", file_csv)
    except TimeoutException:
        logger.warning('Timed out waiting for menu items.')
    except Exception as e:
        logger.error('Error during scraping: %s', e)
    finally:
        menu_driver.quit()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
                        datefmt='%H:%M:%S')
    crawl_nutrition()

