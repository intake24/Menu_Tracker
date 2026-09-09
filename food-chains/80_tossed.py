import json
import os
import re
import time
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

from define_collection_wave import folder, create_collection
from helpers import create_folder, get_chrome_version

# Ensure the collection folder is initialized
if folder is None:
    current_folder = create_collection("Feb_collection_2026")
else:
    current_folder = folder

BASE_URL = "https://tosseduk.vmos.io/store/e062ee16-f9d4-4923-89f5-82abee7dc66c/menu/category/5669e7a7-ca1e-48e4-9e47-63d9a5ecf321/bundles?menuUUID=642a94ec-bea1-42a2-8ed1-79225c70aad6&bundleUUID&upsellDealUUID"
REST_NAME = "TossedUK"

# Outputs
path_out = create_folder('80_Tossed', current_folder)
file_json = os.path.join(path_out, 'tossed_nutrition.json')
file_csv = os.path.join(path_out, 'tossed_nutrition.csv')

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Use a standard user agent
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=options)
    return driver

def get_categories(driver):
    print("Identifying menu categories...")
    categories = []
    
    # The category list's own classes are build-hashed CSS-in-JS names that
    # rotate on every deploy; match on the stable /menu/category/ href
    # pattern instead.
    category_link_selector = "a[href*='/menu/category/']"
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, category_link_selector))
        )
    except:
        print("Timeout waiting for category list.")
        return []

    links = driver.find_elements(By.CSS_SELECTOR, category_link_selector)
    for link in links:
        href = link.get_attribute('href')
        name = link.get_attribute('textContent').strip()
        if href and name:
            categories.append({'url': href, 'name': name})
            
    print(f"Found {len(categories)} categories: {[c['name'] for c in categories]}")
    return categories

def extract_nutrition_from_modal(driver):
    nutrition = {}
    try:
        # Wait for modal to be visible
        modal_selector = ".ReactModal__Content"
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, modal_selector))
        )
        modal = driver.find_element(By.CSS_SELECTOR, modal_selector)
        
        # 1. Item Name - Scoped to modal h1
        try:
            item_name = modal.find_element(By.TAG_NAME, "h1").get_attribute('textContent').strip()
        except:
            item_name = "Unknown Item"

        # 2. Allergens - Unique ID allergens-text
        try:
            # The ID allergens-text is globally unique but we'll still search within the modal if possible
            # or just use driver.find_element if it's standard across the site
            allergens_elem = driver.find_element(By.ID, "allergens-text")
            allergens = allergens_elem.get_attribute('textContent').strip()
        except:
            allergens = ""

        # 3. Nutrition Tab - Switch and extract
        try:
            # Add explicit wait for the nutrition tab to ensure it's loaded
            try:
                nutrition_tab = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "meal-tab-2"))
                )
            except:
                # Fallback: find by text if ID is missing or dynamic
                print(f"    Warning: Could not find meal-tab-2 by ID for {item_name}, trying fallback...")
                tabs = driver.find_elements(By.CSS_SELECTOR, "button")
                nutrition_tab = next((t for t in tabs if "Nutrition" in t.get_attribute('textContent')), None)
            
            if nutrition_tab:
                driver.execute_script("arguments[0].click();", nutrition_tab)
                time.sleep(1.5) # Wait for content transition
                
                # Extract content from modal
                text_content = modal.get_attribute('innerText')
                
                # Map labels to our internal keys
                mappings = {
                    'Energy (kcal)': 'kcal',
                    'Energy (kJ)': 'kj',
                    'Fats': 'fat',
                    'of which saturates': 'satfat',
                    'Carbs': 'carb',
                    'of which sugars': 'sugar',
                    'Proteins': 'protein',
                    'Salt': 'salt'
                }
                
                lines = text_content.split('\n')
                for i, line in enumerate(lines):
                    clean_line = line.strip()
                    if clean_line in mappings:
                        key = mappings[clean_line]
                        if i + 1 < len(lines):
                            val = lines[i+1].strip()
                            nutrition[key] = val
            else:
                print(f"    Warning: Nutrition tab not found for {item_name}")
        except Exception as ne:
            print(f"    Note: Could not extract nutrition for {item_name}: {ne}")

        # Description - Usually first paragraph in modal
        try:
            desc_elem = modal.find_element(By.TAG_NAME, "p")
            description = desc_elem.get_attribute('textContent').strip()
        except:
            description = ""

        # Close the modal
        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label^='Close']")
            driver.execute_script("arguments[0].click();", close_btn)
            WebDriverWait(driver, 5).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, modal_selector)))
        except:
            driver.find_element(By.TAG_NAME, 'body').send_keys(webdriver.Keys.ESCAPE)
            time.sleep(1)
        
        return item_name, description, allergens, nutrition
    except Exception as e:
        print(f"  Error extracting modal data: {e}")
        return None, None, None, None

def scrape_category_items(driver, category):
    print(f"Scraping category: {category['name']}...")
    driver.get(category['url'])
    
    # Wait for items and handle lazy loading
    time.sleep(3)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    
    records = []
    
    # Find all "More details." buttons
    details_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label='More details.']")
    print(f"  Found {len(details_buttons)} items with details.")
    
    for i in range(len(details_buttons)):
        # Re-fetch buttons list to avoid stale element exceptions after modal closes
        current_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label='More details.']")
        if i >= len(current_buttons): break
        
        btn = current_buttons[i]
        
        # Scroll to button to ensure it's clickable
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        time.sleep(0.5)
        
        try:
            driver.execute_script("arguments[0].click();", btn)
        except:
            continue
            
        name, desc, allergens, nutrition = extract_nutrition_from_modal(driver)
        
        if name:
            # Ensure nutrition is a dict even if extraction partially failed
            nut = nutrition if isinstance(nutrition, dict) else {}
            
            record = {
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'rest_name': REST_NAME,
                'menu_name': "Main Menu",
                'menu_section': category['name'],
                'item_name': name,
                'description': desc,
                'allergens': allergens,
                'kj': nut.get('kj', ''),
                'kcal': nut.get('kcal', ''),
                'fat': nut.get('fat', ''),
                'satfat': nut.get('satfat', ''),
                'carb': nut.get('carb', ''),
                'sugar': nut.get('sugar', ''),
                'protein': nut.get('protein', ''),
                'salt': nut.get('salt', '')
            }
            records.append(record)
            
    return records

def crawl_tossed():
    driver = setup_driver()
    try:
        driver.get(BASE_URL)
        categories = get_categories(driver)
        
        all_records = []
        for cat in categories:
            try:
                records = scrape_category_items(driver, cat)
                all_records.extend(records)
                print(f"  Captured {len(records)} items from {cat['name']}")
            except Exception as e:
                print(f"  Error in category {cat['name']}: {e}")
                
        if not all_records:
            print("No data collected.")
            return

        print(f"Total items scraped: {len(all_records)}")
        
        # Save JSON
        with open(file_json, 'w') as f:
            json.dump(all_records, f, indent=2)
            
        # Save CSV
        df = pd.DataFrame(all_records)
        columns = [
            'collection_date', 'rest_name', 'menu_name', 'menu_section', 
            'item_name', 'allergens', 'kj', 'kcal', 'fat', 'satfat', 
            'carb', 'sugar', 'protein', 'salt', 'description'
        ]
        df = df[[c for c in columns if c in df.columns]]
        df.to_csv(file_csv, index=False)
        print(f"Saved results to {file_csv}")

    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_tossed()