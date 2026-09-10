import os
import json
from datetime import date
from typing import Dict, List

import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from define_collection_wave import folder
from helpers import create_folder, headers, clean_text


# Try multiple candidate URLs in case of www/https variants
CANDIDATE_URLS = [
    'http://tkmenus.com/mylocalpub/',
    'https://tkmenus.com/mylocalpub/',
    'http://www.tkmenus.com/mylocalpub/',
    'https://www.tkmenus.com/mylocalpub/',
]
HOMEPAGES = [
    'https://tkmenus.com/',
    'https://www.tkmenus.com/',
]
REST_NAME = 'Town, Pub & Kitchen'

# Outputs
path_out = create_folder('74_TownKitchenPubs', folder)
file_json = os.path.join(path_out, 'townkitchenpubs_items.json')
file_csv = os.path.join(path_out, 'townkitchenpubs_items.csv')


# Use a desktop UA similar to 68_TankPaddle to avoid mobile/dynamic variants
DESKTOP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}


def fetch_html(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=DESKTOP_HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, 'html.parser')


def resolve_menu_url() -> str | None:
    """Try candidate URLs and follow iframe src if present to get the actual menu page."""
    for url in CANDIDATE_URLS:
        try:
            soup = fetch_html(url)
        except Exception:
            continue
        # If page already contains Ten Kites grids, use it
        if soup.select('div.k10-l-grid'):
            return url
        # Otherwise, check for embedded iframe that loads the menu
        iframe = soup.select_one('iframe[src]')
        if iframe:
            src = iframe.get('src')
            if src:
                target = urljoin(url, src)
                try:
                    inner = fetch_html(target)
                    if inner.select('div.k10-l-grid'):
                        return target
                except Exception:
                    pass
    return None


def discover_menu_url_from_home() -> str | None:
    """Scan the tkmenus homepages for anchors that look like brand pages, then probe for grids."""
    keywords = ('mylocal', 'localpub', 'town', 'kitchen', 'pub')
    seen: set[str] = set()
    for home in HOMEPAGES:
        try:
            soup = fetch_html(home)
        except Exception:
            continue
        for a in soup.select('a[href]'):
            href = a.get('href')
            if not href:
                continue
            if any(k in href.lower() for k in keywords):
                url = urljoin(home, href)
                # normalize
                parsed = urlparse(url)
                norm = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if norm in seen:
                    continue
                seen.add(norm)
                try:
                    inner = fetch_html(norm)
                    if inner.select('div.k10-l-grid'):
                        return norm
                    # iframe fallback
                    iframe = inner.select_one('iframe[src]')
                    if iframe:
                        src = urljoin(norm, iframe.get('src'))
                        inner2 = fetch_html(src)
                        if inner2.select('div.k10-l-grid'):
                            return src
                except Exception:
                    continue
    return None


def get_nutrient_value(container, label: str) -> str | None:
    # Find a nutrient item by label text and return its sibling value
    item = container.select_one(f".k10-recipe__nutrients-item span:-soup-contains('{label}')")
    if not item:
        return None
    val = item.find_next_sibling('span')
    return clean_text(val.get_text(strip=True)) if val else None


def parse_page(url: str) -> List[Dict]:
    soup = fetch_html(url)
    items: List[Dict] = []
    grids = soup.select('div.k10-l-grid')
    for grid in grids:
        # Course title is the closest section ancestor's h2
        section = grid.find_parent('section', class_='k10-course')
        cat_name = clean_text(section.find('h2').get_text()) if section and section.find('h2') else None

        name = clean_text(grid.select_one('.k10-recipe__name-val').get_text()) if grid.select_one('.k10-recipe__name-val') else None
        desc_node = grid.select_one('p.k10-recipe__desc')
        description = clean_text(desc_node.get_text(' ', strip=True)) if desc_node else None

        allerg_nodes = grid.select('.k10-recipe__labels-wrapper-content div')
        allergens = [clean_text(a.get_text()) for a in allerg_nodes if clean_text(a.get_text())]

        nutrients_container = grid
        record: Dict = {
            'collection_date': date.today().strftime('%b-%d-%Y'),
            'rest_name': REST_NAME,
            'menu_section': cat_name,
            'item_name': name,
            'item_description': description,
            'allergens': allergens,
            'kcal': get_nutrient_value(nutrients_container, 'Energy (kcal)'),
            'kj': get_nutrient_value(nutrients_container, 'Energy (kJ)'),
            'protein': get_nutrient_value(nutrients_container, 'Protein (g)'),
            'carb': get_nutrient_value(nutrients_container, 'Carbs (g)'),
            'sugar': get_nutrient_value(nutrients_container, 'Sugars (g)'),
            'fat': get_nutrient_value(nutrients_container, 'Fat (g)'),
            'satfat': get_nutrient_value(nutrients_container, 'Saturates (g)'),
            'salt': get_nutrient_value(nutrients_container, 'Salt (g)'),
        }
        items.append(record)
    return items


def save(items: List[Dict]):
    with open(file_json, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    if items:
        pd.DataFrame(items).to_csv(file_csv, index=False)


if __name__ == '__main__':
    target_url = resolve_menu_url()
    if not target_url:
        print('Primary candidates failed. Trying homepage discovery...')
        target_url = discover_menu_url_from_home()
        if not target_url:
            print('Could not resolve menu URL from candidates or homepage. Site structure may have changed.')
            results = []
        else:
            print(f'Parsing menu from discovered URL: {target_url}')
            results = parse_page(target_url)
    else:
        print(f'Parsing menu from: {target_url}')
        results = parse_page(target_url)
    print(f'Scraped {len(results)} items.')
    save(results)
    print(f'Saved: {file_json}')
    if os.path.exists(file_csv):
        print(f'Saved: {file_csv}')
