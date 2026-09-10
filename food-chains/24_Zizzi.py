import json
from datetime import date
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup  # already in requirements

import define_collection_wave as dcw
from helpers import create_folder, PDFDownloader

FULL_MENU_URL = 'https://www.zizzi.co.uk/menus/full-menu'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}


def fetch(url: str) -> str:
    """Helper to GET a URL with basic error handling."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def extract_pdf_urls(html: str) -> List[str]:
    """Extract unique PDF links from the current Zizzi menu page."""
    soup = BeautifulSoup(html, 'html.parser')
    pdf_urls: List[str] = []
    for link in soup.select('a[href]'):
        url = urljoin(FULL_MENU_URL, link['href'].strip())
        if urlparse(url).path.lower().endswith('.pdf') and url not in pdf_urls:
            pdf_urls.append(url)
    return pdf_urls


def _as_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    return value if isinstance(value, list) else []


def _dietary(value: Any) -> Any:
    values = value if isinstance(value, list) else [value]
    labels = [str(item).rstrip('/').split('/')[-1] for item in values if item]
    return '; '.join(labels) if labels else None


def extract_menu_records(html: str, collection_date: str = None) -> List[Dict[str, Any]]:
    """Flatten Zizzi's JSON-LD Menu data into the project CSV record format."""
    collection_date = collection_date or date.today().strftime('%b-%d-%Y')
    soup = BeautifulSoup(html, 'html.parser')
    records: List[Dict[str, Any]] = []

    def add_items(menu_name: str, section: str, sub_sections: List[str], items: Any) -> None:
        for item in _as_list(items):
            if item.get('@type') != 'MenuItem' or not item.get('name'):
                continue
            offers = _as_list(item.get('offers'))
            offer = offers[0] if offers else {}
            price = offer.get('price')
            if price not in (None, ''):
                price = str(price)
                if not price.startswith('£'):
                    price = f'£{price}'
            nutrition = item.get('nutrition') if isinstance(item.get('nutrition'), dict) else {}
            record = {
                'collection_date': collection_date,
                'rest_name': 'Zizzi',
                'menu_name': menu_name,
                'menu_section': section,
                'item_name': item.get('name'),
                'item_id': item.get('id'),
                'kcal': nutrition.get('calories'),
                'item_description': BeautifulSoup(item.get('description') or '', 'html.parser').get_text(' ', strip=True),
                'price': price,
                'dietary': _dietary(item.get('suitableForDiet')),
            }
            if sub_sections:
                record['menu_sub_section'] = ' > '.join(sub_sections)
            records.append(record)

    def walk_sections(menu_name: str, sections: Any, top_section: str = '', sub_sections: List[str] = None) -> None:
        for section in _as_list(sections):
            if section.get('@type') != 'MenuSection':
                continue
            name = (section.get('name') or '').strip()
            current_top = top_section or name
            current_sub_sections = list(sub_sections or [])
            if top_section and name:
                current_sub_sections.append(name)
            add_items(menu_name, current_top, current_sub_sections, section.get('hasMenuItem'))
            walk_sections(menu_name, section.get('hasMenuSection'), current_top, current_sub_sections)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        candidates = _as_list(payload)
        if isinstance(payload, dict):
            candidates += _as_list(payload.get('@graph'))
        for menu in candidates:
            if menu.get('@type') == 'Menu':
                walk_sections((menu.get('name') or 'Menu').strip(), menu.get('hasMenuSection'))
    return records


def crawl_zizzi_menu():
    try:
        print('Fetching full menu page...')
        html = fetch(FULL_MENU_URL)
        path_zizzi = create_folder('24_Zizzi', dcw.folder)
        file_zizzi_json = path_zizzi + '/zizzi_menu.json'
        file_zizzi_csv = path_zizzi + '/zizzi_menu.csv'

        pdf_urls = extract_pdf_urls(html)
        if pdf_urls:
            print(f'Found {len(pdf_urls)} PDF URL(s); downloading...')
            for url in pdf_urls:
                print(f'Found PDF URL {url}')
                filepath = path_zizzi + '/' + url.split('/')[-1]
                PDFDownloader(url, filepath)
                print(f'Downloaded PDF to {filepath}')
        else:
            print('No PDF URLs found.')

        results = extract_menu_records(html)
        print(f'Found {len(results)} menu item(s) in JSON-LD.')
        
        # Save JSON
        with open(file_zizzi_json, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save CSV
        df = pd.DataFrame(results)
        df.to_csv(file_zizzi_csv, index=False)
        
        print(f'Scraped {len(results)} items.')
        print(f'JSON data saved to {file_zizzi_json}')
        print(f'CSV data saved to {file_zizzi_csv}')
        return results
    except Exception as e:
        print(f'Error during Zizzi scraping: {e}')


if __name__ == '__main__':
    crawl_zizzi_menu()
