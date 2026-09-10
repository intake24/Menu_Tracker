import json
import os
import re
from datetime import date
from typing import Dict, List, Optional
from time import sleep

import requests
from bs4 import BeautifulSoup
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder

BASE_START = 'https://www.itsu.com/menu'
BASE_HOST = 'https://www.itsu.com'
REST_NAME = 'Itsu'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

# Outputs
path_out = create_folder('38_Itsu', folder)
file_json = os.path.join(path_out, 'itsu_nutrition.json')
file_csv = os.path.join(path_out, 'itsu_nutrition.csv')


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_categories(html: str) -> List[Dict]:
    """Find category names and links from the main menu page sidebar."""
    soup = BeautifulSoup(html, 'html.parser')
    categories = []
    
    # Use the specific selector identified for sub-menu buttons
    cat_links = soup.select('a.btn.btn-light.btn-sm')
    
    # Fallback: look for category links in common containers
    if not cat_links:
        cat_links = soup.select('nav.category-nav a[href], .category-list a[href]')

    for a in cat_links:
        href = a.get('href')
        name = a.get_text(strip=True)
        if not href or not name:
            continue
        
        # We only want links under /menu/ that are sub-categories
        if '/menu/' not in href:
            continue
            
        url = href if href.startswith('http') else BASE_HOST + href
        if url not in [c['url'] for c in categories] and url != BASE_START:
            categories.append({'name': name, 'url': url})
            
    return categories


def parse_product_links(html: str) -> List[str]:
    """Extract product links from a category page."""
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    # Use the precise selector for product cards
    for a in soup.select('a.base-lined-card.product-listing-card'):
        href = a.get('href')
        if not href: continue
        
        url = href if href.startswith('http') else BASE_HOST + href
        if url not in links:
            links.append(url)
            
    # Fallback
    if not links:
        for a in soup.select('a[href].product-card, a[href].item-link, div.item a[href]'):
            href = a.get('href')
            if not href: continue
            url = href if href.startswith('http') else BASE_HOST + href
            if url not in links and '/menu/' not in url:
                links.append(url)

    return list(set(links))


def parse_product_page(html: str, menu_section: str) -> Dict:
    soup = BeautifulSoup(html, 'html.parser')

    item_name = ""
    h1 = soup.select_one('h1')
    if h1:
        item_name = h1.get_text(strip=True)
        
    description = ""
    # Fixed selector as requested
    desc_node = soup.select_one('p.description')
    if desc_node:
        description = desc_node.get_text(strip=True).replace('\n', ' ')

    # Allergens - using p.contain-info
    contains = ""
    may_contain = ""
    for info in soup.select('p.contain-info'):
        txt = info.get_text().strip()
        lower_txt = txt.lower()
        if 'contains:' in lower_txt:
            contains = txt.split('contains:')[-1].strip()
        elif 'may contain:' in lower_txt:
            may_contain = txt.split('may contain:')[-1].strip()
            
    allergens = f"Contains: {contains}" if contains else ""
    if may_contain:
        allergens += f" | May Contain: {may_contain}" if allergens else f"May Contain: {may_contain}"

    # Nutrition - from dl.nutrition-facts
    nutrition: Dict[str, str] = {}
    
    dl = soup.select_one('dl.nutrition-facts')
    if dl:
        # Map dt to the next dd
        dts = dl.select('dt.fact-title')
        dds = dl.select('dd')
        for i, dt in enumerate(dts):
            label = dt.get_text(strip=True).lower()
            if i < len(dds):
                val = dds[i].get_text(strip=True)
                if 'energy (kcal)' in label: nutrition['kcal'] = val
                elif 'fat (g)' in label: nutrition['fat'] = val
                elif 'of which saturates' in label: nutrition['satfat'] = val
                elif 'carbohydrates (g)' in label: nutrition['carb'] = val
                elif 'of which sugars' in label: nutrition['sugar'] = val
                elif 'fibre (g)' in label: nutrition['fibre'] = val
                elif 'protein (g)' in label: nutrition['protein'] = val
                elif 'salt (g)' in label: nutrition['salt'] = val

    # Clean units and calculate kJ
    kcal_val = 0
    try:
        kcal_str = nutrition.get('kcal', '0').lower().replace('kcal', '').strip()
        kcal_val = float(kcal_str) if kcal_str else 0
    except ValueError:
        pass
        
    kj_val = round(kcal_val * 4.184)
    
    record = {
        'collection_date': date.today().strftime('%b-%d-%Y'),
        'rest_name': REST_NAME,
        'menu_section': menu_section,
        'item_name': item_name,
        'allergens': allergens,
        'kj': f"{kj_val}kj" if kj_val else "",
        'kcal': f"{int(kcal_val)}kcal" if kcal_val else "",
        'fat': nutrition.get('fat', ''),
        'satfat': nutrition.get('satfat', ''),
        'carb': nutrition.get('carb', ''),
        'sugar': nutrition.get('sugar', ''),
        'protein': nutrition.get('protein', ''),
        'salt': nutrition.get('salt', ''),
        'description': description
    }
    
    return record


def crawl_itsu():
    print(f"Starting {REST_NAME} refined scraper...")
    
    try:
        # Initial exploration identified that iterating through sub-categories is better
        start_html = fetch(BASE_START)
        categories = parse_categories(start_html)
    except Exception as e:
        print(f"Failed to fetch main menu: {e}")
        return

    if not categories:
        print("No categories found with primary selector. Using fallback...")
        # Add some known categories if automation fails to find them
        categories = [
            {'name': 'Soups', 'url': f'{BASE_HOST}/menu/soups/'},
            {'name': 'Rice Bowls', 'url': f'{BASE_HOST}/menu/rice-bowls/'},
            {'name': 'Noodles', 'url': f'{BASE_HOST}/menu/noodles/'},
            {'name': 'Sushi & Poké', 'url': f'{BASE_HOST}/menu/sushi-and-poke/'},
            {'name': 'Asian Salads', 'url': f'{BASE_HOST}/menu/asian-salads/'},
            {'name': 'Gyoza & Bao', 'url': f'{BASE_HOST}/menu/gyoza-and-bao/'},
            {'name': 'Sides & Snacks', 'url': f'{BASE_HOST}/menu/sides-and-snacks/'},
            {'name': 'Desserts', 'url': f'{BASE_HOST}/menu/desserts/'},
        ]

    print(f"Processing {len(categories)} categories...")

    records = []
    seen_products = set()

    for cat in categories:
        cat_name = cat['name']
        cat_url = cat['url']
        print(f"Category: {cat_name} ({cat_url})")
        
        try:
            cat_html = fetch(cat_url)
            links = parse_product_links(cat_html)
            
            print(f"  Found {len(links)} products")
            
            for url in links:
                if url in seen_products:
                    continue
                seen_products.add(url)
                
                try:
                    html = fetch(url)
                    record = parse_product_page(html, cat_name)
                    records.append(record)
                    sleep(0.5) 
                except Exception as e:
                    print(f"    Failed product {url}: {e}")
                    
        except Exception as e:
            print(f"  Failed category {cat_name}: {e}")

    if not records:
        print("No records scraped. Verify selectors or connection.")
        return

    print(f"Scraped {len(records)} total items.")
    
    # Save results
    with open(file_json, 'w') as f:
        json.dump(records, f, indent=2)
    
    try:
        df = pd.DataFrame(records)
        columns = [
            'collection_date', 'rest_name', 'menu_section', 'item_name', 
            'allergens', 'kj', 'kcal', 'fat', 'satfat', 'carb', 
            'sugar', 'protein', 'salt', 'description'
        ]
        df = df[[c for c in columns if c in df.columns]]
        df.to_csv(file_csv, index=False)
        print(f"Saved: {file_csv}")
    except Exception as e:
        print(f"CSV error: {e}")


if __name__ == '__main__':
    crawl_itsu()
