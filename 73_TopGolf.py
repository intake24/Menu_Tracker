import io
import os
import json
import re
import time
from datetime import date
from typing import Dict, List

import requests
import pandas as pd
from lxml import html
from pypdf import PdfReader

from define_collection_wave import folder
from helpers import create_folder, headers


BASE = 'https://topgolf.kitchencut.com'
START_URL = f'{BASE}/ecom/menu-ewrft-copy-6613ff9a4db83'
TOPGOLF_UK_URL = 'https://topgolf.com/uk/'
REST_NAME = 'Top Golf'

# Outputs
path_out = create_folder('73_TopGolf', folder)
file_json = os.path.join(path_out, 'topgolf_items.json')
file_csv = os.path.join(path_out, 'topgolf_items.csv')


def fetch(url: str) -> html.HtmlElement:
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return html.fromstring(resp.content)


def normalize_item_name(name: str) -> str:
    name = name.upper().replace('&', ' AND ')
    name = re.sub(r"^NEW\s*(?:['’]?\d{2})?\s*[-–—]*\s*", '', name)
    name = re.sub(r'^(?:SURREY|WAT/CHIG)\s+', '', name)
    name = re.sub(r'\b2[.]0\b', '', name)
    name = re.sub(r'\((?:V|PB)\)', '', name)
    name = re.sub(r'\b(?:V|PB)\b$', '', name)
    name = re.sub(r'[^A-Z0-9]+', ' ', name)
    return ' '.join(name.split())


def parse_menu_calories(text: str) -> Dict[str, str]:
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    calories: Dict[str, str] = {}
    item_pattern = re.compile(
        r"(?m)^([A-Z][A-Z0-9 &'’‘+\-/.]+?)\s*\n"
        r"\s*£[^\n]*?\(([^)\n]*(?:KCAL|CAL\.)[^)\n]*)\)",
        re.IGNORECASE,
    )
    for match in item_pattern.finditer(text):
        name = normalize_item_name(match.group(1))
        values = re.findall(r'(\d+)\s*K?CAL', match.group(2), re.IGNORECASE)
        if not values:
            continue
        if 'BAP OR WRAP' in name and len(values) >= 2:
            calories[normalize_item_name('BIG BREAKFAST BAP')] = values[0]
            calories[normalize_item_name('BIG BREAKFAST WRAP')] = values[1]
        else:
            calories[name] = values[0]

    inline_pattern = re.compile(
        r"(?m)^([A-Z][A-Z0-9 &'’‘+\-/.]+?)\s+\((\d+)\s*KCAL",
        re.IGNORECASE,
    )
    for match in inline_pattern.finditer(text):
        name = normalize_item_name(match.group(1))
        if name and not name.startswith('ADD '):
            calories.setdefault(name, match.group(2))

    priced_inline_pattern = re.compile(
        r"(?m)^([A-Z][A-Z0-9 &'’‘+\-/.]+?)\s+"
        r"£[^\n]*?\((\d+)\s*KCAL",
        re.IGNORECASE,
    )
    for match in priced_inline_pattern.finditer(text):
        name = normalize_item_name(match.group(1))
        if name and not name.startswith('ADD '):
            calories[name] = match.group(2)

    wing_pattern = re.compile(
        r"(?m)^(BULL['’]?S-EYE BBQ SAUCE|FRANK['’]?S BUFFALO|"
        r"KOREAN BBQ & SESAME)\s*\n"
        r"8\s*\((\d+)\s*KCAL[^)]*\)\s*\|\s*14\s*\((\d+)\s*KCAL",
        re.IGNORECASE,
    )
    wing_aliases = {
        'BULL S EYE BBQ SAUCE': 'BBQ',
        'FRANK S BUFFALO': 'BUFFALO',
        'KOREAN BBQ AND SESAME': 'KOREAN',
    }
    for match in wing_pattern.finditer(text):
        sauce = wing_aliases[normalize_item_name(match.group(1))]
        calories[normalize_item_name(f'CHICKEN WINGS X8 {sauce}')] = match.group(2)
        calories[normalize_item_name(f'CHICKEN WINGS X14 {sauce}')] = match.group(3)

    return calories


def calorie_lookup_names(item_name: str) -> List[str]:
    name = normalize_item_name(item_name)
    candidates = [name]
    if not name.startswith('THE '):
        candidates.append(f'THE {name}')
    if name.endswith(' BURGER'):
        candidates.append(name.removesuffix(' BURGER'))
    if name.endswith(' MILKSHAKE') and not name.startswith('VEGAN '):
        candidates.append(name.removesuffix(' MILKSHAKE'))
    if name == 'OPEN DELI':
        candidates.append('OPEN DELI SANDWICH')
    if name == 'CAESAR WRAP':
        candidates.append('CHICKEN CAESAR WRAP')
    if name == 'VEGAN':
        candidates.append('VEGAN')
    return [normalize_item_name(candidate) for candidate in candidates]


def merge_calories(items: List[Dict], calories: Dict[str, str]) -> int:
    matched = 0
    for item in items:
        item['kcal'] = ''
        for candidate in calorie_lookup_names(item.get('item_name', '')):
            if candidate in calories:
                item['kcal'] = calories[candidate]
                matched += 1
                break
    return matched


def current_menu_pdf_url() -> str:
    response = requests.get(TOPGOLF_UK_URL, headers=headers, timeout=30)
    response.raise_for_status()
    paths = re.findall(r'"food_menu":"([^"]+)"', response.text)
    path = next(
        (value for value in paths if 'legacy_menu.pdf' in value),
        paths[0] if paths else '',
    )
    if not path:
        raise RuntimeError('Could not find TopGolf UK menu PDF URL.')
    return f"https://s3.topgolf.com/{path.lstrip('/')}"


def download_pdf_via_google_viewer(pdf_url: str) -> bytes:
    viewer_requests = [
        ('https://docs.google.com/gview', {'embedded': '1', 'url': pdf_url}),
        ('https://docs.google.com/gview', {'url': pdf_url}),
        ('https://docs.google.com/viewerng/viewer', {'url': pdf_url}),
    ]
    for round_number in range(2):
        for viewer_url, params in viewer_requests:
            response = requests.get(
                viewer_url,
                params=params,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            start = response.text.find('https://doc-')
            if start == -1:
                continue
            end = response.text.find('"', start)
            secure_url = response.text[start:end]
            pdf_response = requests.get(secure_url, headers=headers, timeout=60)
            pdf_response.raise_for_status()
            if pdf_response.content.startswith(b'%PDF'):
                return pdf_response.content
        if round_number == 0:
            time.sleep(3)
    raise RuntimeError('Google Viewer could not retrieve the TopGolf menu PDF.')


def fetch_menu_calories() -> Dict[str, str]:
    pdf_url = current_menu_pdf_url()
    pdf_bytes = download_pdf_via_google_viewer(pdf_url)
    pdf_filename = pdf_url.split('/')[-1] or 'topgolf_menu.pdf'
    pdf_path = os.path.join(path_out, pdf_filename)
    with open(pdf_path, 'wb') as f:
        f.write(pdf_bytes)
    print(f'Saved PDF: {pdf_path}')
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    calories = parse_menu_calories(text)
    if not calories:
        raise RuntimeError('No calorie values were found in the TopGolf menu PDF.')
    return calories


def parse_page(url: str) -> List[Dict]:
    tree = fetch(url)
    categories = tree.xpath('//div[@class="table-responsive"]')
    items: List[Dict] = []
    for category in categories:
        # Category name
        cat_name = (category.xpath('normalize-space(.//h4/text())') or '')
        rows = category.xpath('.//tr[contains(@class,"jsDish")]')
        for row in rows:
            item_name = row.xpath('normalize-space(./td[contains(@class,"recipe_name")])')
            allerg_nodes = row.xpath(
                './/td[contains(@class, "active_allergen")]//a'
            )
            allergen_parts: List[str] = []
            for a in allerg_nodes:
                name = (a.xpath('./@data-original-title') or [''])[0]
                status = a.xpath('normalize-space(string())')
                part = f"{status} {name}".strip()
                if part:
                    allergen_parts.append(part)
            allergen_string = ','.join(allergen_parts)

            rec: Dict = {
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'rest_name': REST_NAME,
                'menu_section': cat_name,
                'item_name': item_name,
                'allergens': allergen_string,
            }
            items.append(rec)
    return items


def save(items: List[Dict]):
    with open(file_json, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    if items:
        pd.DataFrame(items).to_csv(file_csv, index=False)


if __name__ == '__main__':
    results = parse_page(START_URL)
    calories = fetch_menu_calories()
    matched = merge_calories(results, calories)
    if not matched:
        raise RuntimeError(
            'TopGolf items were scraped, but none matched the current menu calories.'
        )
    print(f'Scraped {len(results)} items; matched calories for {matched}.')
    save(results)
    print(f'Saved: {file_json}')
    if os.path.exists(file_csv):
        print(f'Saved: {file_csv}')
