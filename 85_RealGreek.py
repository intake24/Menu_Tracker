import os
from datetime import date
from typing import List, Dict

import pandas as pd
import requests
from lxml import html
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from define_collection_wave import folder
from helpers import create_folder, setup_driver, headers, combo_PDFDownload

REST_NAME = 'The Real Greek'
URL = 'https://www.therealgreek.com/menu/'

# Outputs
path_out = create_folder('85_RealGreek', folder)
file_json = os.path.join(path_out, 'real_greek_items.json')
file_jsonl = os.path.join(path_out, 'real_greek_items_JSONL.json')
file_csv = os.path.join(path_out, 'real_greek_items.csv')


def get_text(node, xpath_expr: str) -> str:
    try:
        res = node.xpath(xpath_expr)
        if not res:
            return ''
        val = res[0] if isinstance(res, list) else res
        if hasattr(val, 'text_content'):
            return val.text_content().strip()
        return str(val).strip()
    except Exception:
        return ''


def fetch_tree(url: str) -> html.HtmlElement:
    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()
    return html.fromstring(resp.text)


def parse_static(doc: html.HtmlElement) -> List[Dict]:
    records: List[Dict] = []
    categories = doc.xpath('//h2[@class="h1 text-left scrl-mg-body"]')
    for category in categories:
        cat_name = get_text(category, './text()')
        if not cat_name or cat_name in {'Set Menus', 'Filoxenia Dinner Menu'}:
            continue
        # Primary column items
        items = category.xpath('(./parent::div/following-sibling::div[@class="col-sm-6 col-md-6 col-lg-6"])[1]/div/div')
        # Some items may be under a different container variation
        alt = category.xpath('(./parent::div/following-sibling::div[@class="col-sm-6 col-md-6 col-lg-6 scrl-mg-body"])/div/div')
        if alt:
            items.extend(alt)
        # Hardcoded entries for specific category
        if cat_name == 'SOUVLAKI WRAPS':
            wraps = [
                ['Loukaniko Sausage with Aegean Slaw', '(741kcal)'],
                ['Kalamari with Taramasalata and cucumber ribbons', '(428kcal)'],
                ['Pork with Tzatziki', '(557kcal)'],
                ['Chicken with Greek mustard sauce', '(751kcal)'],
                ['Chicken with Tzatziki', '(620kcal)'],
                ['Lamb Meatballs with minted yoghurt', '(559kcal)'],
                ['Halloumi with minted yoghurt', '(714kcal)'],
                ['Falafel with Tahini', '(684kcal)'],
                ['Vegan Meatballs with Vegan Aioli', '(673kcal)'],
                ['Planted Vegan Chicken with vegan Tzatziki', '(863Kcal)'],
            ]
            for name, dietary in wraps:
                records.append({
                    'collection_date': date.today().strftime('%b-%d-%Y'),
                    'rest_name': REST_NAME,
                    'menu_section': cat_name,
                    'item_name': name,
                    'price': '0.0',
                    'item_description': 'Our gorgeous flatbread filled with chips, fresh tomatoes, red onion and sweet paprika. Please tell your server if you don’t want chips inside! *Kalamari option doesn’t include chips, tomato, onion or paprika.',
                    'dietary': dietary,
                })
            continue
        for item in items:
            item_name = get_text(item, './/h4[@class="the_dish_title"]/text()') or get_text(item, './/h4[@class="the_dish_title "]/text()')
            if not item_name:
                continue
            item_desc = get_text(item, './/div[@class="the_dish_description"]/p/text()')
            dietary = get_text(item, 'normalize-space(.//div[@class="the_dietary_info"]/p/text())').replace('GF', '').replace('V', '').replace('VG', '').replace('G', '')
            if item_name == 'LUXURY SORBET':
                desc = 'Lemon (261kcal) / Mango (283kcal)'
                cals = [int(t.replace('(', '').replace('kcal)', '')) for t in desc.split(' ') if 'kcal' in t]
                dietary = f"({min(cals)}-{max(cals)}kcal)"
                item_desc = desc
            if not item_desc:
                item_desc = get_text(item, './/h4[@class="column"]/text()')
            records.append({
                'collection_date': date.today().strftime('%b-%d-%Y'),
                'rest_name': REST_NAME,
                'menu_section': cat_name,
                'item_name': item_name,
                'price': '0.0',
                'item_description': item_desc,
                'dietary': dietary,
            })
        # RHS hardcoded list from spider
        rhs_items = [
            ['Cold Meze', 'Spicy Feta Dip (Htipiti)', 6.25, 'Roasted pepper and cheese dip, finished with a touch of chilli', '(571kcal)'],
            ['Cold Meze', 'Melitzanosalata', 6.25, 'A light and fragrant blend of smoked aubergine, garlic, red onion, roasted red peppers and lemon.', '(391kcal)'],
            ['Hot Meze', 'Grilled Octopus with Fava', 9.65, 'Chargrilled Octopus, tossed in olive oil, garlic and Greek mountain oregano, served on a bed of Yellow Fava.', '(202kcal)'],
            ['Hot Meze', 'Chicken Monastiraki', 8.75, 'Chicken thigh, marinated with Greek herbs, served with tzatziki, onion and tomatoes.', '(342kcal)'],
            ['Hot Meze', 'BBC Chicken Wings', 7.85, 'Succulent chicken wings marinated in a smoked chilli relish.', '(458kcal)'],
            ['Hot Meze', 'Chicken Skewer', 8.95, 'Chicken, skewered with onions and peppers. Served with Aegean Slaw.', '(260kcal)'],
            ['Hot Meze', 'Lamb Meatballs', 9.00, 'Handmade lamb patties grilled and topped with Greek yoghurt, tomato sauce and onions.', '(435kcal)'],
            ['Hot Meze', 'Lamb Skewer', 9.25, 'Lamb, skewered with onions and peppers. Served with Aegean Slaw.', '(395kcal)'],
            ['Hot Meze', 'Pork Skewer', 8.50, 'Pork, skewered with onions and peppers. Served with Aegean Slaw.', '(722kcal)'],
            ['Hot Meze', 'LOUKANIKO — BEEF & PORK SAUSAGE SKEWER', 7.95, 'Traditional Greek sausage from Thrace, chargrilled and served with Aegean Slaw.', '(613kcal)'],
            ['Hot Meze', 'GREEK MOUSSAKA', 9.50, 'A classic Greek dish – hearty and rich, with lamb mince. Served as a meze portion. Subject to availability.', '(420kcal)'],
            ['Sides & Salads', 'Aegean Slaw', 4.70, 'Thinly shredded cabbage, carrot, red and green peppers, with an olive oil dressing.', '(240kcal)'],
            ['Desserts', 'Luxury Ice-Cream', 4.25, 'Vanilla (419kcal) / Chocolate (433kcal) / Strawberry (312kcal) / Pistachio (413kcal)', '(312-433kcal)'],
            ['Desserts', 'Vegan Vanilla Ice-Cream', 4.25, '', '(525kcal)'],
        ]
        for grp, name, _price, desc, dietary in rhs_items:
            if grp == cat_name:
                records.append({
                    'collection_date': date.today().strftime('%b-%d-%Y'),
                    'rest_name': REST_NAME,
                    'menu_section': cat_name,
                    'item_name': name,
                    'price': '0.0',
                    'item_description': desc,
                    'dietary': dietary,
                })
    return records


def save_outputs(records: List[Dict]):
    df = pd.DataFrame(records)
    df.to_csv(file_csv, index=False)
    df.to_json(file_json, orient='records')
    df.to_json(file_jsonl, orient='records', lines=True)
    print(f"Saved {len(df)} items to:\n- {file_json}\n- {file_jsonl}\n- {file_csv}")


def main():
    # Try requests first; fallback to Selenium for dynamic content
    try:
        doc = fetch_tree(URL)
        recs = parse_static(doc)
    except Exception:
        recs = []

    if not recs:
        # Selenium fallback
        driver = setup_driver()
        try:
            driver.get(URL)
            try:
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//h2[@class='h1 text-left scrl-mg-body']")))
            except TimeoutException:
                pass
            tree = html.fromstring(driver.page_source)
            recs = parse_static(tree)
        finally:
            driver.quit()

    save_outputs(recs)

    # The scraped menu doesn't carry per-item allergen data; the current
    # allergen PDFs linked from the same menu page fill that gap.
    combo_PDFDownload('85_RealGreek', url=URL, keyword='Allergen')


if __name__ == '__main__':
    main()
