"""
Costa Coffee Menu Scraper
Scrapes menu items and nutritional information from https://www.costa.co.uk/menu

This script uses a hybrid approach:
1. First tries to use the GraphQL API directly (faster, no browser needed)
2. Falls back to Selenium browser automation if API access is blocked

The original script had a critical bug where the DataFrame was created outside
the data collection loop, causing only 1 item to be saved.
"""

import json
import logging
import os
import re
from datetime import date
from time import sleep
from typing import List, Dict, Any, Optional

import requests
import pandas as pd

from define_collection_wave import folder, create_collection
from helpers import create_folder

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Auto-initialize collection folder if not already set
# This allows the script to run standalone without running the notebook first
if folder is None:
    create_collection("Feb_collection_2026")
    from define_collection_wave import folder  # Re-import after initialization

# Output paths
REST_NAME = "CostaCoffee"
path_out = create_folder('3_CostaCoffee', folder)
file_json = os.path.join(path_out, 'costacoffee_nutrition.json')
file_csv = os.path.join(path_out, 'costacoffee_nutrition.csv')

MENU_URL = "https://www.costa.co.uk/menu"
API_URL = "https://www.costa.co.uk/api/mdm/"

# Request headers
HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/json',
    'origin': 'https://www.costa.co.uk',
    'referer': 'https://www.costa.co.uk/menu',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'x-channel': 'web',
}

# GraphQL query template for fetching product data
GRAPHQL_QUERY = '''
query MasterProduct {
  masterProducts(groupCodes: %s, effectiveFromDate: null) {
    items {
      id
      brandName
      productDisplayName
      productDescription
      productCode
      groupCode
      images {
        imageStyle
        imageUrl
      }
      variations {
        variationCategoryName
        variationName
      }
      nutritionProducts {
        id
        productCode
        effectiveFromDate
        ingredients
        variations {
          coffeeType
          milkSuffix
          milkType
          serviceDelivery
          size
        }
        dietaryChoices {
          suitableForVegetarians
          suitableForVegans
        }
        allergens {
          celery
          cereals {
            wheat
            rye
            barley
            oat
          }
          crustacean
          egg
          fish
          lupin
          milk
          mollusc
          mustard
          peanut
          sesame
          soya
          sulphite
          treeNuts
          treeNutSource
        }
        nutritionPer100g {
          carbohydrates
          energykCal
          energykJ
          fat
          fibre
          protein
          salt
          saturates
          sugars
          vitaminB6
          vitaminB12
          vitaminC
          zinc
        }
        nutritionPerPortion {
          portionWeight
          carbohydrates
          energykCal
          energykJ
          fat
          fibre
          protein
          salt
          saturates
          sugars
          vitaminB6
          vitaminB12
          vitaminC
          zinc
        }
      }
    }
  }
}
'''


def get_product_codes_from_website() -> List[str]:
    """
    Try to fetch product codes/group codes from the Costa website.
    This fetches the page and extracts product identifiers from the embedded data.
    """
    logger.info("Attempting to fetch product codes from website...")
    
    try:
        response = requests.get(MENU_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        html_content = response.text
        
        # Look for product codes in the page source
        # Costa's Gatsby site often embeds data in script tags
        product_codes = set()
        
        # Pattern to find MP-XXXXXXX product codes
        mp_pattern = r'MP-\d{7}'
        matches = re.findall(mp_pattern, html_content)
        product_codes.update(matches)
        
        # Also look for product names that might be used as group codes
        # These are often in JSON embedded in script tags
        json_pattern = r'productDisplayName["\']?\s*:\s*["\']([^"\']+)["\']'
        name_matches = re.findall(json_pattern, html_content)
        product_codes.update(name_matches)
        
        # Try to find embedded Gatsby data
        gatsby_data_pattern = r'window\.__GATSBY(?:_DATA)?.*?=\s*({.*?});'
        gatsby_matches = re.findall(gatsby_data_pattern, html_content, re.DOTALL)
        for match in gatsby_matches:
            try:
                # Try to parse and extract product info
                mp_in_gatsby = re.findall(mp_pattern, match)
                product_codes.update(mp_in_gatsby)
            except:
                pass
        
        logger.info(f"Found {len(product_codes)} potential product codes from website")
        return list(product_codes)
        
    except Exception as e:
        logger.warning(f"Could not fetch product codes from website: {e}")
        return []


def get_known_product_codes() -> List[str]:
    """
    Return a comprehensive list of known Costa Coffee product codes.
    This is maintained as a fallback when dynamic fetching fails.
    Updated for 2026 menu items.
    """
    # These are group codes that Costa uses for their products
    # Organized by category for easier maintenance
    
    drinks_coffee = [
        "Latte", "Cappuccino", "Americano", "Flat White", "Mocha", 
        "Espresso", "Cortado", "Mocha Cortado", "Macchiato",
        "Spanish Caramelo Latte", "Caramel Latte", "Vanilla Latte",
        "Hazelnut Latte", "Gingerbread & Cream Latte",
    ]
    
    drinks_hot_chocolate = [
        "Hot Chocolate", "White Hot Chocolate", 
        "Terry's Orange Hot Chocolate", "Black Forest Hot Chocolate",
        "Salted Caramel Hot Chocolate",
    ]
    
    drinks_tea = [
        "English Breakfast Tea", "Decaf Tea", "Earl Grey Tea", 
        "Green Tea", "Mint Tea", "Chai Latte",
        "Superfruity Infusion", "Citrus Zing with Vitamin C",
        "Spiced Apple with Vitamin B6", "Mellow Mango with Zinc",
    ]
    
    drinks_cold = [
        "Iced Latte", "Iced Americano Black", "Iced Flat White", "Iced Mocha",
        "Iced Caramel Latte", "Iced Vanilla Latte",
        "Mango & Passion Fruit", "Red Summer Berries",
    ]
    
    drinks_frappe = [
        "Tropical Mango Bubble Frappé", "Strawberries & Cream Frappé",
        "Salted Caramel Frappé", "Salted Caramel Frappé with Coffee",
        "Chocolate Fudge Brownie Frappé", "Chocolate Fudge Brownie Frappé Mocha",
        "Coffee Frappé",
    ]
    
    food_breakfast = [
        "British Pork Sausage Bap", "British Smoked Bacon Bap",
        "Egg Mushroom & Spinach Bap (V)", "Egg & Bacon Roll",
        "Greek Yogurt with Mixed Berry Compote & Granola",
        "Wholegrain Porridge", "Wholegrain Porridge New",
        "Seeded Brown Toast", "White Toast",
    ]
    
    food_lunch = [
        "Turkey Feast Sandwich", "Free Range Egg Mayo Sandwich Without Cress",
        "Wiltshire Ham & Mature Cheddar Toastie", "Cheese & Tomato Toastie",
        "Tuna Melt Panini", "Mozzarella & Tomato Panini",
        "Ham & Cheese Toastie", "Mac & Cheese",
        "Wiltshire Ham & Mature Cheddar Croissant",
        "All Day Breakfast Toastie", "BBQ Chicken Toastie",
    ]
    
    food_pastries = [
        "Croissant", "Almond Croissant (V)", "Chocolate Twist",
        "Cinnamon Bun", "Pain au Chocolat", "Pain aux Raisins",
    ]
    
    food_cakes = [
        "Carrot & Walnut Cake", "Blueberry Muffin", "Lemon Muffin",
        "Terry's Chocolate Orange Muffin", "Chocolate Muffin",
        "Millionaire's Shortbread", "Chocolate Tiffin",
        "Raspberry & Almond Bake", "Bakewell Tart", "Lemon Curd Tart",
        "Lotus Biscoff Cheezecake (Vg)", "All Butter Mince Pie",
        "Fruited Teacake (Vg)", "Belgian Chocolate Brownie",
        "Milk Chocolate Cookie", "White Chocolate Cookie",
    ]
    
    food_biscuits = [
        "Triple Belgian Chocolate Biscuits", "Stem Ginger Biscuits",
        "Fruit & Oat Biscuits", "Jammy Shortbread Biscuits",
        "Mini Shortbread Bites", "Caramel Waffles",
    ]
    
    food_gluten_free = [
        "Millionaire's Shortbread Bar (GF)", "Mince Tart (GF v)",
        "Costa Milk Choc Chunks Gluten Free Brownie", "Fruity Flapjack (GF v)",
    ]
    
    # Product codes (MP-XXXXXXX format)
    mp_codes = [
        "MP-0002247", "MP-0002246", "MP-0002274", "MP-0002248",
        "MP-0000662", "MP-0002245", "MP-0002260", "MP-0002261",
        "MP-0002279", "MP-0000463", "MP-0000701", "MP-0000704",
        "MP-0001671", "MP-0002244", "MP-0001610", "MP-0001669",
        "MP-0000590", "MP-0002234", "MP-0001114", "MP-0001640",
        "MP-0002226", "MP-0002227", "MP-0001608", "MP-0000996",
        "MP-0001271", "MP-0001161", "MP-0001663", "MP-0000447",
        "MP-0002148", "MP-0001087", "MP-0001086", "MP-0001668",
        "MP-0002276", "MP-0001681", "MP-0002229", "MP-0002278",
        "MP-0002275", "MP-0002277", "MP-0002196", "MP-0002280",
        "MP-0002289", "MP-0002290", "MP-0000518", "MP-0000543",
        "MP-0000490", "MP-0002198", "MP-0002199", "MP-0002200", "MP-0002201",
    ]
    
    all_codes = (
        drinks_coffee + drinks_hot_chocolate + drinks_tea + 
        drinks_cold + drinks_frappe +
        food_breakfast + food_lunch + food_pastries + 
        food_cakes + food_biscuits + food_gluten_free +
        mp_codes
    )
    
    return all_codes


def fetch_products_via_graphql(product_codes: List[str], batch_size: int = 25) -> List[Dict]:
    """
    Fetch product data from Costa's GraphQL API.
    Products are fetched in batches to avoid request size limits.
    Includes retry logic with exponential backoff for network errors.
    """
    all_items = []
    max_retries = 3
    
    # Split codes into batches (smaller batches for reliability)
    for i in range(0, len(product_codes), batch_size):
        batch = product_codes[i:i + batch_size]
        batch_json = json.dumps(batch)
        
        query = GRAPHQL_QUERY % batch_json
        payload = {'query': query, 'vars': {}}
        
        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching batch {i//batch_size + 1} ({len(batch)} products), attempt {attempt + 1}...")
                response = requests.post(
                    API_URL, 
                    headers=HEADERS, 
                    json=payload, 
                    timeout=60  # Increased timeout
                )
                response.raise_for_status()
                
                data = response.json()
                items = data.get('data', {}).get('masterProducts', {}).get('items', [])
                
                if items:
                    all_items.extend(items)
                    logger.info(f"Fetched {len(items)} items from batch")
                else:
                    logger.warning(f"No items returned for batch {i//batch_size + 1}")
                
                # Success - break retry loop
                break
                    
            except requests.exceptions.Timeout as e:
                logger.warning(f"Timeout on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                    logger.info(f"Waiting {wait_time}s before retry...")
                    sleep(wait_time)
                else:
                    logger.error(f"Failed after {max_retries} attempts for batch {i//batch_size + 1}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"API request failed for batch {i//batch_size + 1}: {e}")
                if attempt < max_retries - 1:
                    sleep(1)
                    continue
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse response for batch {i//batch_size + 1}: {e}")
                break
        
        # Be nice to the server - longer pause between batches
        sleep(1.0)
    
    return all_items


def parse_product_data(raw_items: List[Dict]) -> List[Dict]:
    """
    Parse raw GraphQL response items into a flat structure for CSV export.
    This fixes the original script's bug where only one item was saved.
    """
    parsed_items = []
    
    for item in raw_items:
        product_name = item.get('productDisplayName', '').strip()
        if not product_name:
            continue
            
        product_description = item.get('productDescription', '')
        if product_description:
            product_description = product_description.replace('\n', ' ').strip()
        
        nutrition_products = item.get('nutritionProducts', [])
        
        if not nutrition_products:
            # Product with no nutrition variants - save basic info
            parsed_items.append({
                'collection_date': date.today().strftime("%b-%d-%Y"),
                'rest_name': REST_NAME,
                'Product_Name': product_name,
                'Product_Description': product_description,
                'Size': '',
                'Milk': '',
                'CoffeeType': '',
                'Ingredients': '',
            })
            continue
        
        # Process each nutrition variant (different sizes, milk types, etc.)
        for nutrition in nutrition_products:
            variations = nutrition.get('variations', {}) or {}
            size = variations.get('size', '') or ''
            milk_type = variations.get('milkType', '') or ''
            coffee_type = variations.get('coffeeType', '') or ''
            
            ingredients = nutrition.get('ingredients', '') or ''
            
            # Build the data record
            record = {
                'collection_date': date.today().strftime("%b-%d-%Y"),
                'rest_name': REST_NAME,
                'Product_Name': product_name,
                'Product_Description': product_description,
                'Size': size,
                'Milk': milk_type,
                'CoffeeType': coffee_type,
                'Ingredients': ingredients,
            }
            
            # Add nutrition per 100g
            nutrition_100g = nutrition.get('nutritionPer100g', {}) or {}
            for key, value in nutrition_100g.items():
                record[f"{key}_Per 100g/ml"] = value
            
            # Add nutrition per portion
            nutrition_portion = nutrition.get('nutritionPerPortion', {}) or {}
            for key, value in nutrition_portion.items():
                if key != 'portionWeight':  # Avoid duplicate
                    record[f"{key}_Per Portion"] = value
            record['portionWeight'] = nutrition_portion.get('portionWeight', '')
            
            # Add allergens
            allergens = nutrition.get('allergens', {}) or {}
            for key, value in allergens.items():
                if isinstance(value, str):
                    # Clean up allergen values
                    if value in ['No', ' ', '']:
                        record[key] = ''
                    else:
                        record[key] = value
                elif isinstance(value, dict):
                    # Handle nested allergen info (e.g., cereals)
                    for sub_key, sub_value in value.items():
                        if sub_value not in ['No', ' ', '']:
                            record[f"{key}_{sub_key}"] = sub_value
            
            # Add dietary choices
            dietary = nutrition.get('dietaryChoices', {}) or {}
            record['Vegetarian'] = dietary.get('suitableForVegetarians', '')
            record['Vegan'] = dietary.get('suitableForVegans', '')
            
            parsed_items.append(record)
    
    return parsed_items


def scrape_with_selenium() -> List[Dict]:
    """
    Fallback scraper using Selenium for browser automation.
    Used when the GraphQL API is blocked or not returning data.
    """
    logger.info("Starting Selenium browser automation...")
    
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait
        from helpers import setup_driver, try_click_accept_cookies
    except ImportError as e:
        logger.error(f"Selenium not available: {e}")
        return []
    
    all_items = []
    
    # Try to setup driver
    try:
        driver = setup_driver()
        # Set a generous page load timeout
        driver.set_page_load_timeout(90)
    except Exception as e:
        logger.error(f"Could not setup browser driver: {e}")
        return []
    
    try:
        logger.info(f"Navigating to {MENU_URL} (this may take a minute...)")
        try:
            driver.get(MENU_URL)
        except Exception as e:
            logger.warning(f"Initial page load timed out or failed: {e}. Trying to continue...")
            
        sleep(5)
        
        # Accept cookies
        try_click_accept_cookies(driver)
        sleep(2)
        
        # Process each category
        for category in ['Drinks', 'Food']:
            logger.info(f"Processing category: {category}")
            
            try:
                # Find category button
                cat_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//button[contains(text(), '{category}')]"))
                )
                driver.execute_script("arguments[0].click();", cat_btn)
                sleep(3)
            except Exception as e:
                logger.warning(f"Could not click category {category}: {e}")
                # Try to find any product to at least start scraping
                pass
            
            # Scroll down to load all products
            logger.info("Scrolling to load products...")
            for _ in range(5):
                driver.execute_script("window.scrollBy(0, 1000);")
                sleep(1)
            
            # Get product items
            # Products are usually in div[role='button'] with an image
            products = driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
            found_data = []
            
            # Extract basic info first to avoid stale elements
            for p in products:
                try:
                    img = p.find_element(By.TAG_NAME, "img")
                    alt = img.get_attribute('alt')
                    if alt:
                        found_data.append({'name': alt, 'element': p})
                except:
                    continue
            
            logger.info(f"Found {len(found_data)} potential products in {category}")
            
            for idx, item in enumerate(found_data):
                product_name = item['name']
                logger.info(f"Processing {idx+1}/{len(found_data)}: {product_name}")
                
                try:
                    # Click the product
                    element = item['element']
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                    sleep(0.5)
                    driver.execute_script("arguments[0].click();", element)
                    
                    # Wait for modal
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='Modal'], [class*='ProductView']"))
                    )
                    sleep(1.5)
                    
                    # Extract data from modal
                    record = {
                        'collection_date': date.today().strftime("%b-%d-%Y"),
                        'rest_name': REST_NAME,
                        'Product_Name': product_name,
                        'Category': category,
                    }
                    
                    # Detailed extraction
                    try:
                        modal = driver.find_element(By.CSS_SELECTOR, "[class*='Modal'], [class*='ProductView']")
                        
                        # Description
                        try:
                            desc = modal.find_element(By.CSS_SELECTOR, "[class*='Description']")
                            record['Product_Description'] = desc.text.strip()
                        except:
                            record['Product_Description'] = ''
                            
                        # Ingredients
                        try:
                            # Try to find ingredients block
                            ing_btn = modal.find_element(By.XPATH, ".//button[contains(., 'Ingredients')]")
                            driver.execute_script("arguments[0].click();", ing_btn)
                            sleep(0.5)
                            ing_text = modal.find_element(By.CSS_SELECTOR, "[class*='Ingredients']").text
                            record['Ingredients'] = ing_text.strip()
                        except:
                            record['Ingredients'] = ''
                            
                        # Nutrition Table
                        try:
                            # Try to expand nutrition accordion
                            nut_btn = modal.find_element(By.XPATH, ".//button[contains(., 'Nutrition')]")
                            driver.execute_script("arguments[0].click();", nut_btn)
                            sleep(0.5)
                        except:
                            pass
                            
                        # Parse nutrition table if present
                        try:
                            rows = modal.find_elements(By.TAG_NAME, "tr")
                            for row in rows:
                                cols = row.find_elements(By.TAG_NAME, "td")
                                if len(cols) >= 2:
                                    key = cols[0].text.strip()
                                    val_100 = cols[1].text.strip()
                                    record[f"{key}_Per 100g/ml"] = val_100
                                    if len(cols) >= 3:
                                        val_portion = cols[2].text.strip()
                                        record[f"{key}_Per Portion"] = val_portion
                        except:
                            # Fallback to regex if table parse fails
                            modal_text = modal.text
                            patterns = {
                                'Energy (kJ)': r'(\d+)\s*kJ',
                                'Energy (kcal)': r'(\d+)\s*kcal',
                                'Fat': r'Fat\s*[\(\n]?\s*(\d+\.?\d*)\s*g',
                                'Carbohydrate': r'Carbohydrate\s*[\(\n]?\s*(\d+\.?\d*)\s*g',
                                'Protein': r'Protein\s*[\(\n]?\s*(\d+\.?\d*)\s*g',
                                'Salt': r'Salt\s*[\(\n]?\s*(\d+\.?\d*)\s*g',
                            }
                            for name, pattern in patterns.items():
                                match = re.search(pattern, modal_text)
                                if match:
                                    record[name] = match.group(1)
                    except Exception as e:
                        logger.debug(f"Error in modal extraction for {product_name}: {e}")
                    
                    all_items.append(record)
                    
                    # Close modal
                    try:
                        close_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Close'], button[class*='Close']")
                        driver.execute_script("arguments[0].click();", close_btn)
                    except:
                        from selenium.webdriver.common.keys import Keys
                        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    sleep(1.0)
                    
                except Exception as e:
                    logger.error(f"Error processing {product_name}: {e}")
                    # Try to close modal just in case
                    try:
                        from selenium.webdriver.common.keys import Keys
                        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    except:
                        pass
                    continue
    
    except Exception as e:
        logger.error(f"Selenium scraper encountered a major error: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass
    
    return all_items


def main():
    """Main entry point for the scraper."""
    import sys
    
    logger.info("Starting Costa Coffee menu scraper")
    
    all_items = []
    
    # Check if --api flag is passed to try API first (disabled by default due to blocking)
    use_api = '--api' in sys.argv
    
    if use_api:
        logger.info("API mode enabled - trying GraphQL API first...")
        # Step 1: Try to get product codes dynamically
        dynamic_codes = get_product_codes_from_website()
        
        # Step 2: Combine with known codes for comprehensive coverage
        known_codes = get_known_product_codes()
        all_codes = list(set(dynamic_codes + known_codes))
        logger.info(f"Using {len(all_codes)} product codes for API query")
        
        # Step 3: Try GraphQL API
        raw_items = fetch_products_via_graphql(all_codes)
        
        if raw_items:
            logger.info(f"GraphQL API returned {len(raw_items)} products")
            all_items = parse_product_data(raw_items)
    
    # Use Selenium if API didn't return data (or wasn't used)
    if not all_items:
        if use_api:
            logger.warning("GraphQL API returned no data, trying Selenium fallback...")
        else:
            logger.info("Using Selenium browser automation (API blocked by Costa)...")
        all_items = scrape_with_selenium()
    
    # Step 4: Save results
    if all_items:
        # Save to JSON
        with open(file_json, 'w', encoding='utf-8') as f:
            json.dump(all_items, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(all_items)} items to {file_json}")
        
        # Save to CSV
        df = pd.DataFrame(all_items)
        df.to_csv(file_csv, index=False, encoding='utf-8')
        logger.info(f"Saved {len(all_items)} items to {file_csv}")
        
        print(f"\n{'='*60}")
        print(f"Successfully scraped {len(all_items)} items from Costa Coffee")
        print(f"JSON saved to: {file_json}")
        print(f"CSV saved to: {file_csv}")
        print(f"{'='*60}\n")
    else:
        logger.error("No items scraped! Please check the logs for errors.")
        print("\nERROR: No items were scraped. The Costa website may have changed.")
        print("Please check the logs and consider updating the scraper.")


if __name__ == "__main__":
    main()
