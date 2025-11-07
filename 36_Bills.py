import json
import os
from datetime import date
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder

BASE_START = "https://menus.tenkites.com/bills/bills03"
BASE_MENU = "https://menus.tenkites.com/bills/bills02?cl=true&mguid={mguid}&internalrequest=true"
REST_NAME = "Bill's"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Outputs
path_out = create_folder("36_Bills", folder)
file_json = os.path.join(path_out, "bills_items.json")
file_csv = os.path.join(path_out, "bills_items.csv")


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def get_menu_guids(home_html: str) -> List[str]:
    soup = BeautifulSoup(home_html, "html.parser")
    guids: List[str] = []

    # 1) CSS selector (expected path)
    for node in soup.select(".k10-menu-selector__option[data-menu-identifier]"):
        mguid = node.get("data-menu-identifier")
        if mguid:
            guids.append(mguid.strip())

    # 2) Generic attribute search fallback
    if not guids:
        for node in soup.find_all(attrs={"data-menu-identifier": True}):
            mguid = node.get("data-menu-identifier")
            if mguid:
                guids.append(mguid.strip())

    # 3) Regex fallback from raw HTML
    if not guids:
        guids = re.findall(r'data-menu-identifier\s*=\s*"([^"]+)"', home_html)

    # unique preserve order
    seen: Set[str] = set()
    uniq = []
    for g in guids:
        if g and g not in seen:
            seen.add(g)
            uniq.append(g)
    return uniq


def text_or_none(node) -> Optional[str]:
    if not node:
        return None
    t = node.get_text(strip=True)
    return t if t else None


def parse_menu_page(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")

    # Global tables list (fallback)
    global_tables = soup.select("table")

    records: List[Dict] = []
    categories = soup.find_all(
        lambda tag: tag.name == "div" and tag.get("class") and any("k10-course_level_1" in c for c in tag.get("class"))
    )

    for idx, category in enumerate(categories):
        cat_name = text_or_none(category.select_one(".k10-course__name-text"))

        # items within category
        items = category.select("div.grid-item")
        if not items:
            items = category.select("div.k10-l-grid-item")

       

        for it in items:
            name = text_or_none(it.select_one("span.k10-recipe__name")) or text_or_none(it.select_one("span.k10-w-recipe__name"))
            desc = text_or_none(it.select_one("span.k10-recipe__desc")) or text_or_none(it.select_one("span.k10-w-recipe__desc"))

            # Choose table: prefer one inside the category; else fallback to global nth
            table = it.select_one("table")
            if not table and idx < len(global_tables):
                table = global_tables[idx]

            kv_pairs: Dict[str, str] = {}
            if table:
                for row in table.select("tr.k10-table__tr, tr"):
                    tds = row.find_all("td")
                    if len(tds) >= 2:
                        key = tds[0].get_text(strip=True)
                        val = tds[1].get_text(strip=True)
                        if key:
                            kv_pairs[key] = val

            item_dict: Dict = {
                "collection_date": date.today().strftime("%b-%d-%Y"),
                "rest_name": REST_NAME,
                "menu_section": cat_name,
                "item_name": name,
                "item_description": desc,
            }
            print(f"Parsed item: {name} in category: {cat_name}")
            item_dict.update(kv_pairs)
            records.append(item_dict)

    return records


def crawl_bills() -> List[Dict]:
    print("Fetching Bills homepage...")
    home = fetch_html(BASE_START)
    guids = get_menu_guids(home)
    print(f"Found {len(guids)} menu GUIDs")

    all_records: List[Dict] = []
    for g in guids:
        url = BASE_MENU.format(mguid=g)
        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"Failed to fetch mguid {g}: {e}")
            continue
        recs = parse_menu_page(html)
        print(f" - {len(recs)} items from mguid {g}")
        all_records.extend(recs)
    return all_records


def save_outputs(items: List[Dict]):
    with open(file_json, "w") as f:
        json.dump(items, f, indent=2)
    try:
        pd.DataFrame(items).to_csv(file_csv, index=False)
    except Exception as e:
        print(f"CSV export failed: {e}")
    print(f"Saved: {file_json}")
    print(f"Saved: {file_csv}")


if __name__ == "__main__":
    data = crawl_bills()
    print(f"Total items scraped: {len(data)}")
    save_outputs(data)
