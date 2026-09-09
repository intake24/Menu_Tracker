import json
from datetime import date
from time import sleep

import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from define_collection_wave import folder
from helpers import create_folder, setup_driver, clean_text


path_nandos = create_folder('10_Nandos', folder)
file_nandos_json = path_nandos + '/nandos_nutrition.json'
file_nandos_csv = path_nandos + '/nandos_nutrition.csv'

def crawl_nandos_nutrition():
    # Setup driver using helper function
    driver = setup_driver()
    
    try:
        url = "https://nandos.co.uk/food/menu/index.html"
        driver.get(url)
        
        # Print page info
        print("Page URL:", driver.current_url)
        print("Page source length:", len(driver.page_source))
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        # sleep(5)  # Give page time to fully load
        
        # Find all product buttons
        item_xpath = '//div/button[contains(@title, "Open product description for")]'
        item_count = len(driver.find_elements(By.XPATH, item_xpath))
        print(f"Found {item_count} menu items")
        
        results = []
        
        for i in range(item_count):
            try:
                items = driver.find_elements(By.XPATH, item_xpath)
                if i >= len(items):
                    break
                item = items[i]
                print(f"Processing item {i+1}/{item_count}")
                
                try:
                    category = clean_text(item.find_element(By.XPATH, './parent::div/preceding-sibling::h2/em').text)
                except:
                    category = "Unknown"

                # Click on item to open modal
                driver.execute_script("arguments[0].click();", item)
                # sleep(2)
                
                # Click on "Nutritional information" tab
                try:
                    nutrition_tab = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, '//ul[@class="tablist"]/li[text()="Nutritional information"]'))
                    )
                    driver.execute_script("arguments[0].click();", nutrition_tab)
                except:
                    print(f"Could not find nutrition tab for item {i+1}")
                    # Close modal and continue
                    try:
                        close_button = driver.find_element(By.XPATH, '//a[@class="close"]')
                        driver.execute_script("arguments[0].click();", close_button)
                    except:
                        pass
                    continue
                
                # Extract nutrition data
                try:
                    product_name_elem = driver.find_element(By.XPATH, '//div[@class="inner"]/h3')
                    product_name = clean_text(product_name_elem.text)
                except:
                    product_name = "Unknown"
                
                try:
                    product_description_elem = driver.find_element(By.XPATH, '//div[@class="inner"]/p')
                    product_description = clean_text(product_description_elem.text)
                except:
                    product_description = ""
                
                try:
                    product_price_elem = driver.find_element(By.XPATH, '//div[@class="inner"]/div[contains(@class,"price")]')
                    product_price = clean_text(product_price_elem.text)
                except:
                    product_price = ""
                
                # Extract nutritional values
                nutrition_data = {}
                try:
                    nutrition_rows = driver.find_elements(By.XPATH, '//div[@class="block n"]/table/tbody/tr')
                    for row in nutrition_rows:
                        try:
                            label_elem = row.find_element(By.XPATH, './/th | .//td[1]')
                            value_elem = row.find_element(By.XPATH, './/th[2] | .//td[2]')
                            
                            # Clean text and remove special characters
                            label = clean_text(label_elem.text)
                            value = clean_text(value_elem.text)
                            
                            # Only add if both label and value are not empty
                            if label and value:
                                nutrition_data[f"{label} per serving"] = value
                        except:
                            continue
                except:
                    print(f"Could not extract nutrition data for item {i+1}")
                
                # Create item dictionary
                item_dict = {
                    'rest_name': 'Nandos',
                    'collection_date': date.today().strftime("%b-%d-%Y"),
                    'Product Name': product_name,
                    'Product Description': product_description,
                    'Product Price': product_price,
                    'Product Category': category,
                }
                
                # Add nutrition data
                item_dict.update(nutrition_data)
                results.append(item_dict)
                
                # Close the modal
                try:
                    close_button = driver.find_element(By.XPATH, '//a[@class="close"]')
                    driver.execute_script("arguments[0].click();", close_button)
                    sleep(1)
                except:
                    print(f"Could not close modal for item {i+1}")
                    
            except Exception as e:
                print(f"Error processing item {i+1}: {str(e)}")
                # Try to close any open modals
                try:
                    close_button = driver.find_element(By.XPATH, '//a[@class="close"]')
                    driver.execute_script("arguments[0].click();", close_button)
                    # sleep(1)
                except:
                    pass
                continue
        
        # Save results to JSON file
        with open(file_nandos_json, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save results to CSV file
        df = pd.DataFrame(results)
        df.to_csv(file_nandos_csv, index=False)
        
        print(f"Scraped {len(results)} items.")
        print(f"JSON data saved to {file_nandos_json}")
        print(f"CSV data saved to {file_nandos_csv}")
        
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_nandos_nutrition()
