import json
import os
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from define_collection_wave import folder
from helpers import create_folder, setup_driver, download_pdf, try_click_accept_cookies, set_driver_timeouts

path = create_folder('20_ChefBrewer', folder)

driver = setup_driver()
set_driver_timeouts(driver)
try_click_accept_cookies(driver)


def scrape_dominos_pdfs():
    """Scrape PDFs from Chec&Brewer's nutrition page"""
    base_url = "https://www.chefandbrewer.com/pubs/cambridgeshire/bridge/menu"
    
    driver = setup_driver()
    
    try:
        print(f"Loading page: {base_url}")
        driver.get(base_url)

        xp = "//*[@class='download-links-legacy-btn var-dark']//button"
        # Wait for page to load
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, xp))
        )
        
        print("Page loaded, found PDF button...")
        try:
        # print heading of the current card
          print("Clicking PDF button (JS)")
          dl_button = driver.find_element(By.XPATH, xp)
          print("PDF button found:", dl_button)
          driver.execute_script("arguments[0].click();", dl_button)
        except Exception:
          try:
            print("Clicking PDF button (native)")
            dl_button.click()
          except Exception:
            print("Failed to click PDF button")
            raise
        # Find all links that might be PDFs
        links = []
        
        # Method 4: Extract JSON payload used in Next.js SPA
        
        # Wait for page to load
        links_el_xp = "//*[@class='download-links-legacy-modal__link']//a"
        try:
          WebDriverWait(driver, 2).until(
              EC.presence_of_element_located((By.XPATH, links_el_xp))
          )
        except Exception as e:
          print("Timeout waiting for PDF links to appear:", str(e))
          raise
        
        links_el = driver.find_elements(By.XPATH, links_el_xp)
        links = [link.get_attribute("href") for link in links_el]
        print("PDF links found, length:", len(links))
        links = list(set(links))  # Remove duplicates
        
        # Print all found links for debugging
        print(f"Found {len(links)} de-duplicated PDF links")
        for link in links:
            print(f"{link}")
        
        # Download PDFs
        downloaded_count = 0
        for i, link_info in enumerate(links, 1):
            url = link_info
            filename = link_info.split('/')[-1].replace('/', '_').replace('\\', '_') + '.pdf'

            print(f"Attempting to download: {filename}")
            print(f"From: {url}")
            
            if download_pdf(url, filename, path):
                downloaded_count += 1
            
            # Small delay between downloads
            time.sleep(1)
        
        print(f"\nScraping completed!")
        print(f"Downloaded {downloaded_count} files to '{path}' folder")
        
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    scrape_dominos_pdfs()
