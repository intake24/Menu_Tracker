import json
import os
import re
import time
from datetime import date
from typing import Dict, List, Optional

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from define_collection_wave import folder, create_collection
from helpers import create_folder, get_chrome_version

# Ensure the collection folder is initialized (e.g., from the environment or default)
if folder is None:
    current_folder = create_collection("Feb_collection_2026")
else:
    current_folder = folder

BASE_URL = "https://www.beefeater.co.uk/en-gb/allergy-nutrition"
REST_NAME = "Beefeater"

# Outputs
path_out = create_folder('16_Beefeater', current_folder)
file_json = os.path.join(path_out, 'beefeater_nutrition.json')
file_csv = os.path.join(path_out, 'beefeater_nutrition.csv')

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-setuid-sandbox")
    options.add_argument("--remote-debugging-port=9222") # Sometimes helps with initialization
    
    # Crucial for sandboxed environments where /tmp/ might be restricted for automatic temp dirs
    user_data_dir = "/tmp/selenium_user_data"
    os.makedirs(user_data_dir, exist_ok=True)
    options.add_argument(f"--user-data-dir={user_data_dir}")
    # Disable features that might trigger unpacking extensions to temp dirs
    options.add_experimental_option("useAutomationExtension", False)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    
    # Use helper if available, otherwise default
    try:
        chrome_version = get_chrome_version()
        print(f"Detected Chrome version: {chrome_version}")
    except:
        pass
        
    driver = webdriver.Chrome(options=options)
    return driver

def get_menu_links(driver):
    print(f"Fetching menu links from {BASE_URL}...")
    driver.get(BASE_URL)
    
    # Wait for content to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/allergy-nutrition/bg-']"))
        )
    except:
        print("Timed out waiting for menu links.")
        return []
    
    menus = []
    # Find active menu links
    anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/allergy-nutrition/bg-']")
    for a in anchors:
        href = a.get_attribute('href')
        if not href:
            continue
            
        # Get text, looking inside <b> tags if necessary
        name = a.text.strip()
        if not name:
            try:
                b_tag = a.find_element(By.TAG_NAME, "b")
                name = b_tag.text.strip()
            except:
                pass
        
        # Filter out placeholders or duplicate IDs
        if not name:
            continue
            
        if href not in [m['url'] for m in menus]:
            menus.append({'url': href, 'name': name})
    
    print(f"Found {len(menus)} valid menu links.")
    return menus

def parse_menu_content(driver, url, menu_name):
    print(f"Scraping menu: {menu_name} ({url})")
    driver.get(url)
    
    # Wait for the first submenu to appear
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[class^='content-SubMenu']"))
        )
    except:
        print(f"Timeout waiting for submenu content on {url}")
        return []

    # Get the page source and parse with BS4
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    records = []
    
    # Find all submenu pills/tabs to associate names
    # Labels have for="SubMenu1", for="SubMenu2", etc.
    submenu_map = {}
    tab_labels = soup.select("label[for^='SubMenu']")
    for label in tab_labels:
        for_attr = label.get('for', '')
        if for_attr:
            # The user wants the text value like "PREMIER INN BREAKFAST" or "74 Sauces"
            submenu_map[for_attr] = label.get_text(strip=True)

    # Iterate through all content-SubMenu containers
    content_divs = soup.select("div[class^='content-SubMenu']")
    for div in content_divs:
        # Get the submenu name from our map
        class_list = div.get('class', [])
        submenu_id = ""
        for c in class_list:
            if c.startswith('content-SubMenu'):
                submenu_id = c.replace('content-', '')
                break
        
        if not submenu_id:
            continue
            
        submenu_name = submenu_map.get(submenu_id, submenu_id)
        
        # Each item is within a div.dish_Content
        dish_divs = div.select("div.dish_Content")
        for dish in dish_divs:
            # Item name
            name_label = dish.select_one(".dishDetails_P.handle label")
            if not name_label:
                continue
            
            item_name = name_label.get_text(strip=True)
            
            # Dietary tags often nearby or inside the handle
            dietary_tags = ""
            tag_spans = name_label.find_all('span')
            if tag_spans:
                dietary_tags = ", ".join([s.get_text(strip=True) for s in tag_spans])
                item_name = item_name.split('\n')[0].strip()

            # The detailed content is in ExColContent
            details = dish.select_one(".ExColContent")
            if not details:
                continue

            # Allergens
            contains = details.select_one("span.dishContains_P2")
            may_contain = details.select_one("span.dishMayContains_P2")
            
            contains_txt = contains.get_text(strip=True) if contains else ""
            may_contain_txt = may_contain.get_text(strip=True) if may_contain else ""
            
            allergens_parts = []
            if contains_txt: allergens_parts.append(f"Contains: {contains_txt}")
            if may_contain_txt: allergens_parts.append(f"May Contain: {may_contain_txt}")
            allergens = " | ".join(allergens_parts)

            # Nutrition from NandATable
            nutrition = {}
            nut_table = details.select_one("table.NandATable")
            if nut_table:
                rows = nut_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        label_txt = cells[0].get_text(strip=True).lower()
                        val = cells[1].get_text(strip=True)
                        
                        if 'energy' in label_txt:
                            parts = val.split('/')
                            if len(parts) == 2:
                                nutrition['kj'] = parts[0].strip()
                                nutrition['kcal'] = parts[1].strip()
                            else:
                                nutrition['kcal'] = val
                        elif 'fat' in label_txt and 'saturates' not in label_txt: nutrition['fat'] = val
                        elif 'saturates' in label_txt: nutrition['satfat'] = val
                        elif 'carbohydrate' in label_txt: nutrition['carb'] = val
                        elif 'sugars' in label_txt: nutrition['sugar'] = val
                        elif 'protein' in label_txt: nutrition['protein'] = val
                        elif 'salt' in label_txt: nutrition['salt'] = val

            record = {
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'rest_name': REST_NAME,
                'menu_name': menu_name,
                'menu_section': submenu_name,
                'item_name': item_name,
                'dietary_tags': dietary_tags,
                'allergens': allergens,
                'kj': nutrition.get('kj', ''),
                'kcal': nutrition.get('kcal', ''),
                'fat': nutrition.get('fat', ''),
                'satfat': nutrition.get('satfat', ''),
                'carb': nutrition.get('carb', ''),
                'sugar': nutrition.get('sugar', ''),
                'protein': nutrition.get('protein', ''),
                'salt': nutrition.get('salt', ''),
                'description': f"Menu: {url.split('/')[-1]}"
            }
            records.append(record)
            
    return records

def crawl_beefeater():
    driver = setup_driver()
    try:
        menus = get_menu_links(driver)
        all_records = []
        
        for menu in menus:
            try:
                records = parse_menu_content(driver, menu['url'], menu['name'])
                all_records.extend(records)
                print(f"  Extracted {len(records)} items from {menu['name']}")
            except Exception as e:
                print(f"  Error processing {menu['name']}: {e}")
        
        if not all_records:
            print("No records found.")
            return

        print(f"Total items scraped: {len(all_records)}")
        
        # Save to JSON
        with open(file_json, 'w') as f:
            json.dump(all_records, f, indent=2)
        print(f"Saved to {file_json}")
        
        # Save to CSV
        df = pd.DataFrame(all_records)
        columns = [
            'collection_date', 'rest_name', 'menu_name', 'menu_section', 
            'item_name', 'allergens', 'kj', 'kcal', 'fat', 'satfat', 
            'carb', 'sugar', 'protein', 'salt', 'description'
        ]
        df = df[[c for c in columns if c in df.columns]]
        df.to_csv(file_csv, index=False)
        print(f"Saved to {file_csv}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_beefeater()
