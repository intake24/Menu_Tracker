"""Collect Cookhouse & Pub's live allergen and nutrition cards."""

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from define_collection_wave import folder
from helpers import create_folder


BASE_URL = "https://www.cookhouseandpub.co.uk/en-gb/allergy-nutrition"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def soup_for(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def menu_urls():
    urls = [
        urljoin(BASE_URL, link["href"])
        for link in soup_for(BASE_URL).select("a[href*='/allergy-nutrition/']")
        if link["href"].rstrip("/").endswith("-web")
    ]
    if not urls:
        raise RuntimeError("Cookhouse & Pub published no nutrition menu links")
    return list(dict.fromkeys(urls))


def parse_menu(url):
    records = []
    for card in soup_for(url).select("details.recipe, div.dish_Content"):
        title = card.select_one(".title, .dishDetails_P label")
        name = next(title.stripped_strings, "") if title else ""
        if not name:
            continue
        values = {
            cells[0].get_text(" ", strip=True).lower(): cells[1].get_text(" ", strip=True)
            for row in card.select("table tr")
            if len(cells := row.select("td")) >= 2
        }
        energy = re.search(r"([\d,.]+)\s*kJ\s*/\s*([\d,.]+)\s*kcal", values.get("energy", ""), re.I)
        contains_node = card.select_one(".dishContains_P2")
        may_contain_node = card.select_one(".dishMayContains_P2")
        blocks = card.select(".kv .block")
        contains = contains_node.get_text(" ", strip=True) if contains_node else (
            blocks[0].select_one(".v").get_text(" ", strip=True) if blocks else None
        )
        may_contain = may_contain_node.get_text(" ", strip=True) if may_contain_node else (
            blocks[1].select_one(".v").get_text(" ", strip=True) if len(blocks) > 1 else None
        )
        section = card.get("data-submenu")
        if not section:
            section_node = card.find_parent(class_=re.compile(r"^content-SubMenu"))
            section = section_node.select_one(".subMenu_P").get_text(" ", strip=True) if section_node and section_node.select_one(".subMenu_P") else None
        records.append({
            "collection_date": date.today().strftime("%b-%d-%Y"),
            "rest_name": "Cookhouse & Pub",
            "menu_name": url.rsplit("/", 1)[-1],
            "menu_section": section,
            "item_name": name,
            "dietary": card.get("data-diet"),
            "allergens": contains,
            "may_contain": may_contain,
            "kj": energy.group(1) if energy else None,
            "kcal": energy.group(2) if energy else None,
            "fat": values.get("fat"),
            "satfat": values.get("saturates"),
            "carb": values.get("carbohydrates"),
            "sugar": values.get("sugars"),
            "protein": values.get("protein"),
            "salt": values.get("salt"),
        })
    return records


if __name__ == "__main__":
    records = [record for url in menu_urls() for record in parse_menu(url)]
    if not records:
        raise RuntimeError("Cookhouse & Pub nutrition pages contained no recipes")
    output = Path(create_folder("49_CookhousePub", folder))
    (output / "cookhousepub_nutrition.json").write_text(json.dumps(records, indent=2) + "\n")
    pd.DataFrame(records).to_csv(output / "cookhousepub_nutrition.csv", index=False)
    print(f"Scraped {len(records)} Cookhouse & Pub menu items")
