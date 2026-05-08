# Newer version aims to replace dependency on Scrapy framework
import json
from datetime import date
from time import sleep
import pandas as pd
from bs4 import BeautifulSoup

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from define_collection_wave import folder
from helpers import create_folder, setup_driver, clean_text

path_wagamama = create_folder('15_Wagamama', folder)
file_wagamama_json = path_wagamama + '/wagamama_nutrition.json'
file_wagamama_csv = path_wagamama + '/wagamama_nutrition.csv'


def resolve_nuxt_ref(nuxt_data, value):
    """Resolve one devalue/Nuxt payload reference."""
    if isinstance(value, int) and 0 <= value < len(nuxt_data):
        return nuxt_data[value]
    return value


def build_intolerance_lookup(nuxt_data):
    """Map Wagamama intolerance/dietary ids to readable labels."""
    lookup = {}
    for entry in nuxt_data:
        if not isinstance(entry, dict) or "Id" not in entry or "Desc" not in entry:
            continue

        intol_id = resolve_nuxt_ref(nuxt_data, entry.get("Id"))
        desc = clean_text(resolve_nuxt_ref(nuxt_data, entry.get("Desc")))
        if isinstance(intol_id, int) and desc:
            lookup[intol_id] = desc

    return lookup


def parse_category(orig_name):
    """Infer the Wagamama menu/category label from the payload item name."""
    if not orig_name or " - " not in orig_name:
        return ""
    return clean_text(orig_name.split(" - ", 1)[0])


def parse_allergens(nuxt_data, item, intolerance_lookup):
    intol_refs = resolve_nuxt_ref(nuxt_data, item.get("Intols"))
    if not isinstance(intol_refs, list):
        return ""

    allergens = []
    seen = set()
    for intol_ref in intol_refs:
        intol = resolve_nuxt_ref(nuxt_data, intol_ref)
        if not isinstance(intol, dict):
            continue

        intol_id = resolve_nuxt_ref(nuxt_data, intol.get("Id"))
        label = intolerance_lookup.get(intol_id, str(intol_id) if intol_id else "")
        label = clean_text(label)
        if label and label not in seen:
            allergens.append(label)
            seen.add(label)

    return ", ".join(allergens)


def parse_nutrition(nuxt_data, item, item_record):
    nutr_refs = resolve_nuxt_ref(nuxt_data, item.get("Nutrs"))
    if not isinstance(nutr_refs, list):
        return

    for nutr_ref in nutr_refs:
        nutr = resolve_nuxt_ref(nuxt_data, nutr_ref)
        if not isinstance(nutr, dict):
            continue

        nutrient = clean_text(resolve_nuxt_ref(nuxt_data, nutr.get("Desc")))
        per_serving = clean_text(resolve_nuxt_ref(nuxt_data, nutr.get("PerServ")))
        per_100g = clean_text(resolve_nuxt_ref(nuxt_data, nutr.get("Per100g")))

        if nutrient:
            item_record[nutrient] = per_serving
            item_record[nutrient + "_100g"] = per_100g


def parse_wagamama_nuxt_data(nuxt_data):
    """Extract Wagamama menu items from the current Nuxt SSR payload."""
    intolerance_lookup = build_intolerance_lookup(nuxt_data)
    results = []
    seen_item_ids = set()

    for entry in nuxt_data:
        if not isinstance(entry, dict):
            continue
        if not {"Ident", "Name", "OrigName", "Desc", "Nutrs"}.issubset(entry):
            continue

        item_id = resolve_nuxt_ref(nuxt_data, entry.get("Ident"))
        if item_id:
            if item_id in seen_item_ids:
                continue
            seen_item_ids.add(item_id)

        item_name = clean_text(resolve_nuxt_ref(nuxt_data, entry.get("Name")))
        item_description = clean_text(resolve_nuxt_ref(nuxt_data, entry.get("Desc")))
        orig_name = clean_text(resolve_nuxt_ref(nuxt_data, entry.get("OrigName")))
        if not item_name:
            continue

        item_record = {
            "rest_name": "Wagamama",
            "collection_date": date.today().strftime("%b-%d-%Y"),
            "category": parse_category(orig_name),
            "item_name": item_name,
            "item_description": item_description,
            "allergens": parse_allergens(nuxt_data, entry, intolerance_lookup),
        }
        parse_nutrition(nuxt_data, entry, item_record)
        results.append(item_record)

    return results


def extract_wagamama_payload_items(page_source):
    """Read menu data from Wagamama's embedded Nuxt payload."""
    soup = BeautifulSoup(page_source, "html.parser")
    payload = soup.find("script", id="__NUXT_DATA__")
    if not payload or not payload.string:
        raise ValueError("Could not find Wagamama __NUXT_DATA__ payload")

    return parse_wagamama_nuxt_data(json.loads(payload.string))


def crawl_wagamama_nutrition():
    # Setup driver using helper function
    driver = setup_driver()
    
    try:
        driver.get("https://www.wagamama.com/menu?category=sides-sharing")
        print("Page URL:", driver.current_url)
        print("Page source length:", len(driver.page_source))
        
        # Wait for page to load
        print("Waiting for page to load...")
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("Page loaded.")
        # Handle cookie consent if present, but don't block if absent/un-clickable
        try:
            consent_btn = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.ID, 'onetrust-accept-btn-handler'))
            )
            try:
                WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.ID, 'onetrust-accept-btn-handler')))
                consent_btn.click()
                print("Cookie consent accepted")
                sleep(0.3)
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", consent_btn)
                    print("Cookie consent accepted via JS")
                    sleep(0.3)
                except Exception:
                    print("Cookie banner present but could not be clicked; continuing without accepting")
        except Exception:
            print("No cookie consent banner; continuing")
        
        # Wagamama now embeds the menu and nutrition data in the Nuxt SSR
        # payload. The rendered item-card class names are hashed and volatile.
        results = extract_wagamama_payload_items(driver.page_source)
        print(f"Extracted {len(results)} items from Nuxt payload")
        
        # Save results to JSON file
        with open(file_wagamama_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Scraped {len(results)} items. Data saved to {file_wagamama_json}.")
        # Save results to CSV file
        if results:
            df = pd.DataFrame(results)
            df.to_csv(file_wagamama_csv, index=False)
            print(f"Data also saved to CSV: {file_wagamama_csv}")
        else:
            print("No data to save to CSV")

    except Exception as e:
        print(f"Error during scraping: {str(e)}")
    
    finally:
        driver.quit()


if __name__ == "__main__":
    crawl_wagamama_nutrition()
