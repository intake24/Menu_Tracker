"""Hungry Horse: kcal/price from the brand's menu API and allergens from SmartChef.

Hungry Horse menus are the same in every pub, so one reference pub is used:
Bradmore Arms (SmartChef/menu-API site id 1953). Nutrition is kcal-only.
"""

import json
import re
from datetime import date

import pandas as pd
import requests
from bs4 import BeautifulSoup

from define_collection_wave import folder
from helpers import create_folder

REST_NAME = "Hungry Horse"
SITE_ID = 1953
MENU_API = f"https://www.hungryhorse.co.uk/api/menus/getmenus/{SITE_ID}"
SMARTCHEF = "https://www.smartchef.co.uk"
SMARTCHEF_INDEX = f"{SMARTCHEF}/brands/HungryHorse?siteid={SITE_ID}"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
TIMEOUT = 60

path_out = create_folder("54_HungryHorse", folder)
today = date.today().strftime("%b-%d-%Y")


def _get(url, **kwargs):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kwargs)
    resp.raise_for_status()
    return resp


def collect_nutrition():
    rows = []
    for menu in _get(MENU_API).json():
        for category in menu["categories"]:
            for product in category["products"]:
                for portion in product.get("portions") or [{}]:
                    rows.append({
                        "collection_date": today,
                        "rest_name": REST_NAME,
                        "menu": menu["name"],
                        "menu_section": category["name"],
                        "item_name": product["name"],
                        "description": product.get("description", ""),
                        "portion": portion.get("portionName") or portion.get("name", ""),
                        "kcal": portion.get("calories"),
                        "price": portion.get("price"),
                        "dietary_options": ", ".join(map(str, product.get("dietaryOptions") or [])),
                    })
    return rows


def _menu_ids():
    soup = BeautifulSoup(_get(SMARTCHEF_INDEX).text, "html.parser")
    menus = {}
    for a in soup.find_all("a", href=re.compile(r"LoadMenu\('")):
        guid = re.search(r"LoadMenu\('([^']+)'", a["href"]).group(1)
        name = a.get_text(" ", strip=True)
        if name:
            menus.setdefault(guid, name)
    return menus


def _flag(item, attr):
    return (item.get(attr) or "").upper() == "TRUE"


def collect_allergens():
    rows = []
    for guid, menu_name in _menu_ids().items():
        html = _get(
            f"{SMARTCHEF}/Brands/HungryHorseMenuItems",
            params={"menuid": guid, "filter": "''"},
        ).text
        soup = BeautifulSoup(html, "html.parser")
        section_names = {
            a["id"].removesuffix("-Button"): a.get_text(" ", strip=True)
            for a in soup.select("a.tabLinks[id]")
        }
        for item in soup.select("div.menuItem"):
            texts = [s.get_text(" ", strip=True) for s in item.find_all("span")]
            if not texts:
                continue
            contains = next((t for t in texts if t.startswith("Contains:")), "")
            others = [t for t in texts if not t.startswith("Contains:")]
            tab = item.find_parent("div", class_="tabContent")
            rows.append({
                "collection_date": today,
                "rest_name": REST_NAME,
                "menu": menu_name,
                "menu_section": section_names.get(tab.get("id") if tab else None, ""),
                "item_name": others[0] if others else "",
                "description": others[1] if len(others) > 1 else "",
                "allergens": contains.removeprefix("Contains:").strip(),
                "vegetarian": _flag(item, "data-vegetarian"),
                "vegan": _flag(item, "data-vegan"),
                "gluten_free": _flag(item, "data-glufree"),
            })
    return rows


def _write(rows, stem):
    if not rows:
        raise RuntimeError(f"No {stem} rows collected; source layout may have changed")
    with open(f"{path_out}/{stem}.json", "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
    pd.DataFrame(rows).to_csv(f"{path_out}/{stem}.csv", index=False)
    print(f"{stem}: {len(rows)} rows")


if __name__ == "__main__":
    _write(collect_nutrition(), "hungryhorse_nutrition")
    _write(collect_allergens(), "hungryhorse_allergens")
