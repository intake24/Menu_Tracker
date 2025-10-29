import json
from datetime import date
from time import sleep

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from define_collection_wave import folder
from helpers import create_folder, setup_driver, clean_text

path_allbarone = create_folder('29_AllBarOne', folder)
file_allbarone_json = path_allbarone + '/allbarone_nutrition.json'
file_allbarone_csv = path_allbarone + '/allbarone_nutrition.csv'

START_URL = 'https://www.allbarone.co.uk/food-and-drink'


def _try_click_accept_cookies(driver) -> None:
    """Attempt to accept cookies banner to unblock interactions."""
    try:
        print("Trying to accept cookies banner if present...")
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
                    print("Cookies banner accepted.")
                    break
                except Exception:
                    print("Failed to accept cookies banner.")
                    continue
    except Exception:
        pass


def _get_visible_text(el, driver) -> str:
    """Return best-effort visible text from an element (text, innerText, textContent)."""
    try:
        t = (el.text or "").strip()
        if t:
            return t
    except Exception:
        pass
    try:
        t = driver.execute_script(
            "return (arguments[0].innerText || arguments[0].textContent || '').trim();", el
        )
        if t:
            return t
    except Exception:
        pass
    return ""


def _extract_food_name_from_card(card, driver) -> str:
    """Try multiple selectors and fallbacks to extract a food name from a card."""
    candidate_xpaths = [
        ".//h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6",
        # ".//*[contains(translate(@class,'TITLE','title'),'title')]",
        # ".//*[contains(translate(@class,'NAME','name'),'name')]",
        # ".//a[contains(translate(@class,'TITLE','title'),'title')]",
        # ".//a[contains(translate(@class,'NAME','name'),'name')]",
    ]
    for xp in candidate_xpaths:
        try:
            for el in card.find_elements(By.XPATH, xp):
                txt = clean_text(_get_visible_text(el, driver))
                if txt:
                    return txt
        except Exception:
            continue

# def _extract_from_modal_if_any(driver) -> str:
#     """If a modal/dialog is open, try to read its heading/title."""
#     try:
#         modal = WebDriverWait(driver, 3).until(
#             EC.presence_of_element_located(
#                 (By.XPATH, "//*[contains(@class,'Modal') or contains(@class,'modal') or contains(@role,'dialog')]")
#             )
#         )
#         for xp in [
#             ".//h1 | .//h2 | .//h3 | .//h4",
#             ".//*[contains(translate(@class,'TITLE','title'),'title')]",
#             ".//*[contains(@role,'heading')]",
#         ]:
#             els = modal.find_elements(By.XPATH, xp)
#             for el in els:
#                 txt = clean_text(_get_visible_text(el, driver))
#                 if txt:
#                     return txt
#     except Exception:
#         pass
#     return ""


def crawl_allbarone_nutrition():
    driver = setup_driver()
    _try_click_accept_cookies(driver)
    results = []
    try:
        driver.get(START_URL)
        print('Page URL:', driver.current_url)
        print('Waiting for menu items to load...')
        WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.XPATH, "//*[@class='image parbase section']") )
        )
        sleep(0.5)
        print('Menu items loaded.')

        def wait_for_menu_grid():
            WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//*[@class='image parbase section']"))
            )

        def get_food_menu_urls():
            menu_els = driver.find_elements(By.XPATH, "//*[@class='image parbase section']//a")
            # return an array of URL
            menu_urls = [el.get_attribute("href") for el in menu_els]
            print(f'  menu_els: {len(menu_els)}')
            return menu_urls


        def find_food_cards(timeout, menu_url):
            """Try multiple selectors to find food cards on a menu page."""
            driver.get(menu_url)
            selectors = [
                # (By.CSS_SELECTOR, "div.MenuItem__wrapper"),
                (By.XPATH, "//div[contains(@class,'MenuItem__wrapper')]") ,
                # (By.XPATH, "//div[contains(@class,'menu-item') or contains(@class,'MenuItem')]") ,
                # (By.CSS_SELECTOR, "[data-component='menu-item']"),
            ]
            for by, sel in selectors:
                try:
                    els = WebDriverWait(driver, timeout).until(
                        EC.presence_of_all_elements_located((by, sel))
                    )
                    if els:
                        return els
                except TimeoutException:
                    continue
            return []

        food_menus_urls = get_food_menu_urls()
        
        print(f'Found {len(food_menus_urls)} menu items')

        for idx, menu_url in enumerate(food_menus_urls):
            try:
                # Find food cards, with a fallback to a generic 'menu' link
                foods = find_food_cards(timeout=8, menu_url=menu_url)
                print(f"Found {len(foods)} foods in menu {idx+1}, url: {menu_url}")
                for f_idx, food in enumerate(foods):
                    try:
                        # Ensure the card is in view
                        # try:
                        #     driver.execute_script("arguments[0].scrollIntoView({block:'center'});", food)
                        #     sleep(0.2)
                        # except Exception:
                        #     pass

                        # 1) Try to read directly from the card
                        food_name = _extract_food_name_from_card(food, driver)

                        # # 2) If still empty, try opening detail/modal then read title
                        # if not food_name:
                        #     try:
                        #         driver.execute_script("arguments[0].click();", food)
                        #         try:
                        #             WebDriverWait(driver, 5).until(
                        #                 EC.presence_of_element_located(
                        #                     (By.XPATH, "//*[contains(@class,'Modal') or contains(@class,'modal') or contains(@role,'dialog')]")
                        #                 )
                        #             )
                        #         except TimeoutException:
                        #             pass
                        #         modal_name = _extract_from_modal_if_any(driver)
                        #         if modal_name:
                        #             food_name = modal_name
                        #     except Exception:
                        #         pass

                        # # 3) As a final fallback, take whole-card text
                        # if not food_name:
                        #     food_name = clean_text(_get_visible_text(food, driver))

                        # Debug: raw heading text if present
                        raw_heading = ""
                        try:
                            el = food.find_element(By.XPATH, ".//h1 | .//h2 | .//h3 | .//h4")
                            raw_heading = (el.text or el.get_attribute("innerText") or "").strip()
                        except Exception:
                            pass
                        print(f"  [{f_idx+1}/{len(foods)}] Food: {food_name or '<empty>'}")

                        # Close detail/modal if opened
                        try:
                            close_btn = driver.find_element(By.XPATH, "//div[contains(@class,'Modal__close')] | //button[contains(., 'Close')]")
                            driver.execute_script("arguments[0].click();", close_btn)
                            sleep(0.2)
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"  Error processing food item: {e}")
                        continue
                # Return to the main grid of menu tiles
                try:
                    driver.back()
                    wait_for_menu_grid()
                    sleep(0.2)
                except Exception:
                    pass
            except Exception as e:
                print(f"Error processing item {idx+1}: {e}")
                try:
                    driver.back()
                    wait_for_menu_grid()
                except Exception:
                    pass
                continue

        # Save outputs
        with open(file_allbarone_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Scraped {len(results)} items. Data saved to {file_allbarone_json}")

        if results:
            pd.DataFrame(results).to_csv(file_allbarone_csv, index=False)
            print(f"Data also saved to CSV: {file_allbarone_csv}")
    except TimeoutException:
        print('Timed out waiting for menu items.')
    except Exception as e:
        print(f'Error during scraping: {e}')
    finally:
        driver.quit()


if __name__ == '__main__':
    crawl_allbarone_nutrition()
