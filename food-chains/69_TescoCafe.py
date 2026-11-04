import os
import re
import time
import json
from datetime import date
from typing import Dict, List

import pandas as pd
from fake_useragent import UserAgent
from lxml import html
from pypdf import PdfReader

from define_collection_wave import folder
from helpers import create_folder, setup_driver

BASE_URL = 'https://www.tesco.com/zones/tesco-cafe'
REST_NAME = 'Tesco Cafe'
BLOCK_RETRIES = 3
BLOCK_BACKOFF_SECONDS = 30

# Outputs
path_out = create_folder('69_TescoCafe', folder)
file_json = os.path.join(path_out, 'tescocafe_items.json')
file_csv = os.path.join(path_out, 'tescocafe_items.csv')


def fetch(driver, url: str) -> html.HtmlElement:
    """Load a URL in the browser session and return its lxml tree.

    tesco.com blocks plain `requests` traffic (TLS/bot-fingerprint
    detection returns 403) but serves a real browser session normally, so
    this loads pages through Selenium instead.
    """
    driver.get(url)
    return html.fromstring(driver.page_source)


def get_category_links(driver) -> List[Dict[str, str]]:
    """Find category links in the 'Browse our menus' section.

    Returns a list of dicts with keys: url, category
    """
    tree = fetch(driver, BASE_URL)
    # Locate the h2 containing 'Browse our menus', then the first following div and anchors beneath
    menus = tree.xpath("//h2[contains(normalize-space(.), 'Browse our menus')]/parent::div/following-sibling::div[1]//a")
    results: List[Dict[str, str]] = []
    for a in menus:
        href = a.get('href') or ''
        # Some links may be relative
        if href.startswith('/'):
            href = f'https://www.tesco.com{href}'
        label = a.get('aria-label') or a.text_content().strip()
        if href:
            results.append({'url': href, 'category': label})
    return results


def parse_category_page(driver, url: str, category_label: str) -> List[Dict]:
    """Parse a category page to extract item cards as per the original spider logic."""
    tree = fetch(driver, url)
    # The original spider targeted a deeply classed grid column; we use a robust contains selector
    # and then grab section children representing items.
    sections = tree.xpath('//div[contains(@class, "beans-grid__column")]//section')
    records: List[Dict] = []

    for sec in sections:
        item_all = sec.get('aria-label') or ''
        if not item_all:
            # some sites put aria-label on inner nodes; fallback to first child
            inner = sec.xpath('.//*[@aria-label][1]/@aria-label')
            item_all = inner[0] if inner else ''
        if not item_all:
            # skip if no aria-label to parse
            continue
        # Mirror original parsing rules
        try:
            desc = ','.join(item_all.split(',')[1:-1])
            item_name_all = item_all.split(',')[0].strip()
            name = item_name_all.split('£')[0]
            # extract kcal tokens
            new_cal_list = [i.strip('.').strip('\n') for i in item_all.split(' ') if 'kcal' in i]
            if len(new_cal_list) > 1:
                new_cal_range = [int(i.replace('kcal','').strip(',').strip('(').strip(')')) for i in new_cal_list]
                new_cal = f"{min(new_cal_range)}-{max(new_cal_range)}kcal"
            else:
                new_cal = new_cal_list[0] if new_cal_list else ''
            if name == 'BLT Baguette':
                new_cal = [i.split('.')[0].replace(' ','') for i in item_all.split(',') if 'kcal' in i]
            if name == 'Tuna':
                name = name + desc
                desc = name
        except Exception:
            # fallbacks
            name = item_all.split(',')[0].strip()
            desc = ''
            new_cal = ''

        record: Dict[str, str] = {
            'collection_date': date.today().strftime('%b-%d-%Y'),
            'rest_name': REST_NAME,
            'menu_section': category_label,
            'item_name': name,
            'item_description': desc,
            'kcal': new_cal,
            'url': url,
        }
        records.append(record)

    return records


def download_allergen_pdf(driver):
    """Find and download the current GB allergen matrix PDF.

    The page (already loaded by get_category_links) embeds direct links to
    several PDFs; pick the GB (not Northern Ireland) allergen matrix. The
    PDF host is behind the same bot-fingerprint block as the main site, so
    the browser session downloads it (Chrome auto-downloads PDFs when
    ``download_dir`` is set on the driver) rather than a plain request.
    """
    urls = re.findall(r'href="([^"]*\.pdf[^"]*)"', driver.page_source)
    candidates = [u for u in urls if 'allergen' in u.lower() and 'ni+allergen' not in u.lower()]
    if not candidates:
        print('No GB allergen matrix PDF link found.')
        return None
    pdf_url = candidates[0]
    before = {f for f in os.listdir(path_out) if f.lower().endswith('.pdf')}
    driver.get(pdf_url)
    for _ in range(20):
        after = {f for f in os.listdir(path_out) if f.lower().endswith(('.pdf', '.crdownload'))}
        finished = {f for f in after if not f.endswith('.crdownload')}
        if finished - before:
            print(f'Downloaded allergen PDF: {sorted(finished - before)}')
            return os.path.join(path_out, sorted(finished - before)[0])
        time.sleep(1)
    print('Timed out waiting for allergen PDF download.')
    return None


def _key(name: str) -> str:
    """Match key: drop '(v)'/'(vg)' tags, punctuation and case differences."""
    return re.sub(r'[^a-z0-9]+', ' ', re.sub(r'\([^)]*\)', '', name.lower().replace('&', ' and '))).strip()


def pdf_kcal(pdf_path: str) -> Dict[str, str]:
    """Map lower-cased item name -> 'N kcal' from the allergen matrix.

    tesco.com no longer shows calories on the menu pages; they are only
    published per serving in the matrix PDF (rows like 'Item name 730 kcal Y Y ...').
    """
    text = '\n'.join(p.extract_text() for p in PdfReader(pdf_path).pages)
    rows = re.findall(r'^\s*(\S.*?)\s+(\d+) kcal', text, re.M)
    return {_key(name): f'{kcal}kcal' for name, kcal in rows}


def fill_kcal(items: List[Dict], pdf_path) -> None:
    if not pdf_path:
        return
    table = pdf_kcal(pdf_path)
    for item in items:
        if not item['kcal']:
            item['kcal'] = table.get(_key(item['item_name']), '')
    print(f"kcal filled for {sum(bool(i['kcal']) for i in items)}/{len(items)} items")


def crawl_tescocafe() -> List[Dict]:
    """Crawl with a fresh browser per attempt: Tesco's bot manager intermittently
    serves an "Error" interstitial, and a new session often gets through."""
    for attempt in range(BLOCK_RETRIES):
        items = _crawl_once()
        if items:
            return items
        if attempt < BLOCK_RETRIES - 1:
            wait = BLOCK_BACKOFF_SECONDS * 2 ** attempt
            print(f'No items (attempt {attempt + 1}/{BLOCK_RETRIES}); retrying with a new browser in {wait}s')
            time.sleep(wait)
    return []


def _crawl_once() -> List[Dict]:
    items: List[Dict] = []
    # setup_driver picks a random UA that can be a mobile one; Tesco serves
    # its "Error" interstitial to those (mobile UA on a desktop browser), so
    # force a desktop Chrome UA (the last --user-agent flag wins).
    desktop_ua = UserAgent(browsers=['Chrome'], platforms='desktop').random
    driver = setup_driver(download_dir=path_out, extra_chrome_args=[f'--user-agent={desktop_ua}'])
    try:
        cats = get_category_links(driver)
        if not cats:
            print('No category links found. The site structure may have changed or content is client-rendered.')
        for cat in cats:
            try:
                records = parse_category_page(driver, cat['url'], cat['category'])
                items.extend(records)
            except Exception as e:
                print(f"Failed to parse category {cat['category']} ({cat['url']}): {e}")

        # Re-fetch the landing page (parse_category_page navigated away from it)
        # so the PDF links are back in the page source before downloading.
        fetch(driver, BASE_URL)
        fill_kcal(items, download_allergen_pdf(driver))
    finally:
        driver.quit()
    return items


def save(items: List[Dict]):
    with open(file_json, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    if items:
        pd.DataFrame(items).to_csv(file_csv, index=False)


if __name__ == '__main__':
    items = crawl_tescocafe()
    print(f'Scraped {len(items)} items.')
    if not items:
        raise RuntimeError('No Tesco Cafe items scraped (bot block or site change); not writing an empty result')
    save(items)
    print(f'Saved: {file_json}')
    if os.path.exists(file_csv):
        print(f'Saved: {file_csv}')
