import json
import re
from datetime import date
from typing import List, Dict, Any

import pandas as pd
import requests
from bs4 import BeautifulSoup  # already in requirements

from define_collection_wave import folder
from helpers import create_folder, PDFDownloader

path_ask = create_folder('25_Ask', folder)
file_ask_json = path_ask + '/ask_menu.json'
file_ask_csv = path_ask + '/ask_menu.csv'

FULL_MENU_URL = 'https://www.askitalian.co.uk/menus/full-menu'


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

def fetch(url: str) -> str:
    """Helper to GET a URL with basic error handling."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text

def find_pdf_urls(html: str) -> List[str]:
    """Extract the allergen PDF links embedded in the Next.js page data."""
    matches = re.findall(
        r'https://cdn\.sanity\.io/files/[^"\\\s]+?\.pdf',
        html,
    )
    return list(dict.fromkeys(matches))


def extract_next_menu_records(html: str) -> List[Dict[str, Any]]:
    """Extract the complete item data embedded in the Next.js flight payload."""
    soup = BeautifulSoup(html, 'html.parser')
    collection_date = date.today().strftime('%b-%d-%Y')

    for script in soup.find_all('script'):
        script_text = script.string or script.get_text()
        prefix = 'self.__next_f.push('
        if not script_text.startswith(prefix):
            continue

        try:
            _, payload = json.loads(script_text[len(prefix):-1])
            _, raw_data = payload.split(':', 1)
            component = json.loads(raw_data.rstrip('\n'))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

        if (
            not isinstance(component, list)
            or len(component) < 4
            or not isinstance(component[3], dict)
        ):
            continue

        props = component[3]
        sections = props.get('menuSections')
        if not sections:
            continue

        menu_name = (props.get('page') or {}).get('title') or 'Menu'
        records: List[Dict[str, Any]] = []
        for section in sections:
            groups = [section]
            while groups:
                group = groups.pop(0)
                groups.extend(group.get('children', []) or [])
                for item in group.get('items', []) or []:
                    records.append({
                        'collection_date': collection_date,
                        'rest_name': 'ask',
                        'menu_name': menu_name,
                        'menu_section': section.get('title'),
                        'item_name': item.get('name'),
                        'item_id': item.get('id'),
                        'kcal': item.get('kcal'),
                        'item_description': item.get('description'),
                        'price': item.get('price'),
                        'dietary': item.get('dietary'),
                    })
        return records

    return []


def extract_menu_records(html: str) -> List[Dict[str, Any]]:
    """Extract menu records from the page's schema.org Menu data."""
    next_records = extract_next_menu_records(html)
    if next_records:
        return next_records

    soup = BeautifulSoup(html, 'html.parser')
    records: List[Dict[str, Any]] = []
    collection_date = date.today().strftime('%b-%d-%Y')

    for script in soup.find_all('script', {'type': 'application/ld+json'}):
        try:
            menu = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(menu, dict) or menu.get('@type') != 'Menu':
            continue

        menu_name = menu.get('name')
        for section in menu.get('hasMenuSection', []) or []:
            section_title = section.get('name')
            for item in section.get('hasMenuItem', []) or []:
                nutrition = item.get('nutrition') or {}
                calorie_text = str(nutrition.get('calories', ''))
                calorie_match = re.search(r'[\d,]+', calorie_text)
                offers = item.get('offers') or {}
                price = offers.get('price')
                dietary = [
                    value.rsplit('/', 1)[-1]
                    for value in item.get('suitableForDiet', []) or []
                ]
                records.append({
                    'collection_date': collection_date,
                    'rest_name': 'ask',
                    'menu_name': menu_name,
                    'menu_section': section_title,
                    'item_name': item.get('name'),
                    'item_id': item.get('@id'),
                    'kcal': (
                        int(calorie_match.group().replace(',', ''))
                        if calorie_match else None
                    ),
                    'item_description': item.get('description'),
                    'price': float(price) if price not in (None, '') else None,
                    'dietary': dietary,
                })

    return records


def crawl_ask_menu():
  try:
    print('Fetching full menu page...')
    html = fetch(FULL_MENU_URL)

    pdf_urls = find_pdf_urls(html)
    print(f'Found {len(pdf_urls)} allergen PDF link(s)')
    for pdf_url in pdf_urls:
      filename = pdf_url.rsplit('/', 1)[-1].split('?', 1)[0]
      filepath = path_ask + '/' + filename
      PDFDownloader(pdf_url, filepath)
      print(f'Downloaded PDF from {pdf_url} to {filepath}...')

    results = extract_menu_records(html)
    
    # Save JSON
    with open(file_ask_json, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save CSV
    df = pd.DataFrame(results)
    df.to_csv(file_ask_csv, index=False)
    
    print(f'Scraped {len(results)} items.')
    print(f'JSON data saved to {file_ask_json}')
    print(f'CSV data saved to {file_ask_csv}')
  except Exception as e:
      print(f'Error during ask scraping: {e}')


if __name__ == '__main__':
    crawl_ask_menu()
