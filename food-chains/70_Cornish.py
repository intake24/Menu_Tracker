import os
import json
import re
from datetime import date
from typing import Dict, List

import requests
import pandas as pd
from lxml import html

from define_collection_wave import folder
from helpers import create_folder, headers, combo_PDFDownload


BASE_URL = 'https://thecornishbakery.com/pages/allergens'
REST_NAME = 'The Cornish Bakery'

# Outputs
path_out = create_folder('70_Cornish', folder)
file_json = os.path.join(path_out, 'cornish_items.json')
file_csv = os.path.join(path_out, 'cornish_items.csv')


def manual_csv_safe_string(input_string: str | None) -> str | None:
    """Replicate the original sanitization used in the Scrapy spider.

    - Strips surrounding quotes and whitespace
    - Escapes embedded quotes by doubling them
    - Replaces newlines with literal \n
    Note: Pandas will quote fields correctly when writing CSV; this
    is kept to preserve the original output style.
    """
    if input_string is None:
        return None
    escaped_string = input_string.strip('" \n').replace('"', '""').replace('\n', '\\n')
    return escaped_string


def fetch(url: str) -> html.HtmlElement:
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return html.fromstring(resp.content)


def parse_allergens_page(url: str) -> List[Dict]:
    tree = fetch(url)
    sections = tree.xpath('//section[@class="accordion-section section-padding"]')
    items: List[Dict] = []

    for section in sections:
        section_name = (section.xpath('.//summary[@class="accordion__title h6"]/text()') or [''])[0]
        paragraphs = section.xpath('.//div[@class="faq-list__item-content"]/p')
        for p in paragraphs:
            # Product name is in <strong>
            item_name_list = p.xpath('./strong/text()')
            item_name = item_name_list[0] if item_name_list else ''

            # Skip blank markers
            if item_name == '\xa0' or not item_name.strip():
                continue

            # Description from text nodes directly under <p> (excludes <strong>)
            text_nodes = [t.strip() for t in p.xpath('./text()') if t and t.strip()]
            description = ','.join(text_nodes)

            # Extract kcal token if present
            kcal_match = re.search(r'[0-9]+kcal', description)
            kcal = kcal_match.group(0) if kcal_match else None

            record = {
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'rest_name': REST_NAME,
                'item_name': manual_csv_safe_string(item_name),
                'menu_section': manual_csv_safe_string(section_name),
                'item_description': manual_csv_safe_string(description),
                'kcal': kcal,
            }
            items.append(record)

    return items


def save(items: List[Dict]):
    with open(file_json, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    if items:
        pd.DataFrame(items).to_csv(file_csv, index=False)


if __name__ == '__main__':
    try:
        results = parse_allergens_page(BASE_URL)
        print(f'Scraped {len(results)} items.')
        save(results)
        print(f'Saved: {file_json}')
        if os.path.exists(file_csv):
            print(f'Saved: {file_csv}')
    except Exception as e:
        print(f'Failed to scrape {REST_NAME}: {e}')

    # The site's per-item allergen data doesn't include a full nutrition
    # breakdown; the current allergen matrix PDF on the products page fills
    # that gap.
    combo_PDFDownload('70_Cornish', url='https://thecornishbakery.com/products/', keyword='Allergen')
