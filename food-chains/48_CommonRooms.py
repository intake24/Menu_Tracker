import json
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from define_collection_wave import folder
from helpers import create_folder


LANDING_URL = "https://www.socialpubandkitchen.co.uk/library-leeds/food-and-drink"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MenuTracker/1.0)"}


def fetch(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text


def discover_menu_url(html):
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        if "allergen and dietary information" in link.get_text(" ", strip=True).lower():
            return link["href"]
    raise RuntimeError("Social Pub & Kitchen allergen menu link was not found")


def nutrient(item, label):
    for block in item.select("div.k10-recipe__nutrients-item"):
        spans = block.find_all("span")
        if len(spans) >= 2 and label in spans[0].get_text(" ", strip=True):
            return spans[1].get_text(" ", strip=True).replace(",", "")
    return None


def parse_menu(html):
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for item in soup.select("div.k10-l-grid"):
        name = item.select_one("span.k10-recipe__name-val")
        if not name:
            continue
        section = item.find_parent("section", class_="k10-course")
        labels = item.select_one("div.k10-recipe__labels-wrapper-content")
        records.append({
            "collection_date": date.today().strftime("%b-%d-%Y"),
            "rest_name": "Common Room / Social Pub & Kitchen",
            "menu_section": section.find("h2").get_text(" ", strip=True) if section and section.find("h2") else None,
            "item_name": name.get_text(" ", strip=True),
            "item_description": item.select_one("p.k10-recipe__desc").get_text(" ", strip=True) if item.select_one("p.k10-recipe__desc") else None,
            "allergens": list(labels.stripped_strings) if labels else [],
            "kcal": nutrient(item, "Energy (kcal)"),
            "kj": nutrient(item, "Energy (kJ)"),
            "protein": nutrient(item, "Protein (g)"),
            "carb": nutrient(item, "Carbs (g)"),
            "sugar": nutrient(item, "Sugars (g)"),
            "fat": nutrient(item, "Fat (g)"),
            "satfat": nutrient(item, "Saturates (g)"),
            "salt": nutrient(item, "Salt (g)"),
        })
    return records


def main():
    menu_url = discover_menu_url(fetch(LANDING_URL))
    records = parse_menu(fetch(menu_url))
    if not records:
        raise RuntimeError(f"No menu records found at {menu_url}")
    output_dir = Path(create_folder("48_CommonRooms", folder))
    (output_dir / "commonrooms_nutrition.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    pd.DataFrame(records).to_csv(output_dir / "commonrooms_nutrition.csv", index=False)
    print(f"Saved {len(records)} successor-menu records to {output_dir}")


if __name__ == "__main__":
    main()
