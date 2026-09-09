import os
import json
from datetime import date
from typing import Dict, List

import requests
import pandas as pd
from lxml import html

import define_collection_wave as dcw
from define_collection_wave import folder as collection_folder
from helpers import create_folder, headers

BASE = 'https://timhortons.co.uk'
START_URL = f'{BASE}/menu'
REST_NAME = 'Tim Hortons'
FOLDER_KEY = '72_TimHortons'

# Ensure the collection folder is initialized (fallback for standalone runs)
if not collection_folder:
    dcw.create_collection("default_collection")

# Outputs
path_out = create_folder(FOLDER_KEY, dcw.folder)
file_json = os.path.join(path_out, 'timhortons_items.json')
file_csv = os.path.join(path_out, 'timhortons_items.csv')


def fetch(url: str) -> html.HtmlElement:
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return html.fromstring(resp.content)


def get_categories_and_items() -> List[Dict[str, str]]:
    """Return a list of dicts with category, item_name, and item_url."""
    tree = fetch(START_URL)
    blocks = tree.xpath('//div[@class="menu-items box-grid small-up-2 medium-up-3 large-up-4"]')
    results: List[Dict[str, str]] = []
    for block in blocks:
        items = block.xpath('./a')
        if not items:
            continue
        cat_name = (items[0].xpath('./div/@class') or [''])[0].replace('anchor', '')
        for a in items:
            item_name = (a.xpath('./p/text()') or [''])[0]
            href = (a.xpath('./@href') or [''])[0]
            if not href:
                continue
            if href.startswith('/'):
                item_url = BASE + href
            else:
                item_url = BASE + '/' + href
            results.append({'category': cat_name, 'item_name': item_name, 'url': item_url})
    return results


def _parse_nutrition(tree: html.HtmlElement, page_url: str,
                     category: str, item_name: str,
                     size_label: str = '') -> Dict:
    """Extract one nutrition record from an already-fetched page tree."""
    rows = tree.xpath('//div[@class="information_detail"]//table[1]//tr')
    # Serving size from the row whose header contains 'Serving Size'
    servingsize = None
    for r in rows:
        header = ''.join(r.xpath('.//th//text()')).strip()
        if 'Serving Size' in header:
            servingsize = (r.xpath('.//td/text()') or [''])[0]
            break

    display_name = f'{item_name} ({size_label})' if size_label else item_name
    record: Dict = {
        'collection_date': date.today().strftime('%b-%d-%Y'),
        'rest_name': REST_NAME,
        'menu_section': category,
        'menu_id': page_url.split('/information/')[-1],
        'item_name': display_name,
        'item_size': size_label,
        'servingsize': servingsize,
        'url': page_url,
    }

    # Remaining rows map headers to either _perserving, _percent depending on values
    # Skip the first two rows (typically headers/serving size), follow original logic
    for r in rows[2:]:
        header = ''.join(r.xpath('.//th//text()')).strip()
        values = [v.strip() for v in r.xpath('.//td/text()') if v and v.strip()]
        if not header:
            continue
        if len(values) == 2:
            record[f'{header}_perserving'] = values[0]
            record[f'{header}_percent'] = values[1]
        elif len(values) == 1:
            if values[0].endswith('%') or '%' in values[0]:
                record[f'{header}_percent'] = values[0]
            else:
                record[f'{header}_perserving'] = values[0]

    return record


# Maps size CSS class → human-readable label
_SIZE_LABELS = {'s': 'Small', 'm': 'Medium', 'l': 'Large'}


def parse_item(item_url: str, category: str, item_name: str) -> List[Dict]:
    """Parse an item page, returning one record per available size.

    If the page has no size selector (e.g. food items), a single record is
    returned.  For beverages with S / M / L options, each size is fetched and
    returned as its own record.
    """
    tree = fetch(item_url)

    # Detect size options (div.sizes containing links)
    sizes_div = tree.xpath('//div[contains(@class, "sizes")]')
    if sizes_div:
        size_links = sizes_div[0].xpath('.//div[contains(@class, "s") or contains(@class, "m") or contains(@class, "l")]')
        records: List[Dict] = []
        for div in size_links:
            css_cls = (div.get('class') or '').strip()
            label = _SIZE_LABELS.get(css_cls, css_cls.upper())
            anchor = div.xpath('.//a')
            if not anchor:
                continue
            href = anchor[0].get('href', '')
            is_active = 'active' in (anchor[0].get('class') or '')
            if is_active:
                # Already on this page – parse the current tree directly
                records.append(_parse_nutrition(tree, item_url, category, item_name, label))
            else:
                # Fetch the size-specific page
                try:
                    size_tree = fetch(href)
                    records.append(_parse_nutrition(size_tree, href, category, item_name, label))
                except Exception as e:
                    print(f"  Failed to fetch size {label} for {item_name}: {e}")
        return records
    else:
        # No size options – single record
        return [_parse_nutrition(tree, item_url, category, item_name)]


def crawl_timh():
    items: List[Dict] = []
    for meta in get_categories_and_items():
        try:
            recs = parse_item(meta['url'], meta['category'], meta['item_name'])
            items.extend(recs)
        except Exception as e:
            print(f"Failed to parse item {meta['url']}: {e}")
    return items


def save(items: List[Dict]):
    with open(file_json, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    if items:
        pd.DataFrame(items).to_csv(file_csv, index=False)


if __name__ == '__main__':
    results = crawl_timh()
    print(f'Scraped {len(results)} items.')
    save(results)
    print(f'Saved: {file_json}')
    if os.path.exists(file_csv):
        print(f'Saved: {file_csv}')
