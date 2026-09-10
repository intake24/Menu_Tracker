import json
import os
import re
from datetime import date
from typing import Dict, List, Optional, Set

import requests
from bs4 import BeautifulSoup
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder

REST_NAME = "Honest Burgers"
BASE_START = "https://menus.tenkites.com/honestburgers/honestburgers"
# Ten Kites often uses XX03 for landing and XX02 for menu pages; include candidates
CANDIDATE_MENU_URLS = [
    # Primary: site indicates mguid param on the same path
    lambda g: f"{BASE_START}?mguid={g}",
    # Variant with cl=true (common flag on Ten Kites)
    lambda g: f"{BASE_START}?cl=true&mguid={g}",
    # Internal widget render often returns fully expanded markup server-side
    lambda g: f"{BASE_START}?internalrequest=true&mguid={g}",
    lambda g: f"{BASE_START}?internalrequest=true&cl=true&mguid={g}",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


SUITABILITY_LABELS = {"Vegetarian", "Vegan", "Halaal", "Gluten Free"}

# Outputs
path_out = create_folder("86_HonestBurger", folder)
file_json = os.path.join(path_out, "honest_burgers_items.json")
file_csv = os.path.join(path_out, "honest_burgers_items.csv")


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def get_menu_guids(home_html: str) -> List[str]:
    """Extract Ten Kites menu GUIDs from the landing page.
    Common patterns:
    - .k10-menu-selector__option[data-menu-identifier]
    - Generic data-menu-identifier attributes
    - Regex as last resort
    """
    soup = BeautifulSoup(home_html, "html.parser")
    guids: List[str] = []

    for node in soup.select(".k10-menu-selector__option[data-menu-identifier]"):
        mguid = node.get("data-menu-identifier")
        if mguid:
            guids.append(mguid.strip())

    if not guids:
        for node in soup.find_all(attrs={"data-menu-identifier": True}):
            mguid = node.get("data-menu-identifier")
            if mguid:
                guids.append(mguid.strip())

    if not guids:
        guids = re.findall(r'data-menu-identifier\s*=\s*"([^"]+)"', home_html)

    # Deduplicate preserve order
    seen: Set[str] = set()
    uniq = []
    for g in guids:
        if g and g not in seen:
            seen.add(g)
            uniq.append(g)
    return uniq


def text_or_none(el) -> Optional[str]:
    if not el:
        return None
    t = el.get_text(strip=True)
    return t if t else None

def sanitize_key(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


"""Removed table/grid fallback parsing to keep implementation concise and widget-focused."""


def parse_menu_page(html_text: str) -> List[Dict]:
    """Parse one Ten Kites menu page into records.
    This variant is tuned for Honest Burgers where nutrition is presented in tables.
    It will:
      1) Iterate course/section containers and parse any tables within as row items
      2) If no sections or no rows found, parse all top-level tables on the page similarly
      3) As a last fallback, attempt the grid-item approach used by Bills
    """
    soup = BeautifulSoup(html_text, "html.parser")

    all_records: List[Dict] = []

    # 0) Ten Kites widget recipe-card parsing (desktop view). Avoid duplicates by excluding mobile variant.
    # Courses/sections
    courses = soup.select("div.k10-course.k10-w-course, div.k10-course_l1.k10-w-course, div.k10-course")
    for course in courses:
        section_title = (
            text_or_none(course.select_one(".k10-w-course__name-text"))
            or text_or_none(course.select_one(".k10-course__name-text"))
            or text_or_none(course.select_one(".k10-w-course__name"))
            or text_or_none(course.select_one(".k10-course__name"))
        )
        recipes = course.select(
            "div.k10-w-recipe.k10-recipe_menu-item.k10-w-recipe__info, div.k10-recipe.k10-w-recipe.k10-recipe_menu-item.k10-w-recipe__info"
        )
        for r in recipes:
            name = (
                text_or_none(r.select_one("span.k10-w-recipe__name"))
                or text_or_none(r.select_one(".k10-recipe__name .k10-w-recipe__name"))
                or text_or_none(r.select_one("span.k10-recipe__name"))
            )
            desc = text_or_none(r.select_one("span.k10-w-recipe__desc, span.k10-recipe__desc"))
            calories = r.get("data-calories")
            recipe_guid = r.get("data-guid")
            recipe_id = r.get("data-recipe-id")
            # Collect suitability labels only
            label_names = [
                n.get("data-label-name")
                for n in r.select(".k10-recipe__label[data-label-name]")
                if n.get("data-label-name") in SUITABILITY_LABELS
            ]
            price_el = r.select_one(".k10-w-recipe__price, .k10-recipe__price, .k10-w-course__sell-price")
            price = text_or_none(price_el)

            # Inline nutrient values present on the row (in DOM)
            nutrients_raw: Dict[str, Optional[str]] = {}
            for n_el in r.select(".k10-recipe__label_nutrient"):
                n_name = (n_el.get("data-nutrient-name") or "").strip()
                n_val = text_or_none(n_el)
                if not n_name or n_val is None:
                    continue
                key = sanitize_key(n_name.replace("kCal", "kcal").replace("kJ", "kj"))
                nutrients_raw[key] = n_val

            # Extract allergens from the recipe details card using <strong> content
            allergens_str: Optional[str] = None
            if recipe_guid:
                # Prefer within the same course, else search whole soup
                card = None
                for d in course.select("div.k10-recipe-card, div.k10-w-recipe-card"):
                    if d.get("data-guid") == recipe_guid:
                        card = d
                        break
                if card is None:
                    card = next((d for d in soup.select("div.k10-recipe-card, div.k10-w-recipe-card") if d.get("data-guid") == recipe_guid), None)
                if card is not None:
                    # Heuristic: allergen list appears enclosed in a <strong> tag
                    strong_tags = card.select("strong")
                    indic = {"gluten", "wheat", "milk", "egg", "eggs", "soya", "soy", "sesame", "fish", "crustaceans", "celery", "mustard", "lupin", "molluscs", "peanut", "peanuts", "nuts", "sulphite", "sulphites", "onion", "garlic"}
                    for s_el in strong_tags:
                        t = s_el.get_text(" ", strip=True)
                        tl = t.lower()
                        if tl == "allergens":
                            # Try next strong as the list
                            ns = s_el.find_next("strong")
                            if ns and ns is not s_el:
                                cand = ns.get_text(" ", strip=True)
                                if any(k in cand.lower() for k in indic):
                                    allergens_str = cand.strip()
                                    break
                            # Else try immediate sibling text
                            sib = s_el.next_sibling
                            if sib:
                                cand = str(sib).strip(" :\n\t")
                                if any(k in cand.lower() for k in indic):
                                    allergens_str = cand
                                    break
                        else:
                            # Strong that itself contains a list of allergens
                            if ("," in tl or ")" in tl) and any(k in tl for k in indic):
                                allergens_str = t
                                break

            if name:
                rec: Dict = {
                    "collection_date": date.today().strftime("%b-%d-%Y"),
                    "rest_name": REST_NAME,
                    "menu_section": section_title,
                    "item_name": name,
                    "item_description": desc,
                    "calories": calories,
                    "price": price,
                    "recipe_guid": recipe_guid,
                    "recipe_id": recipe_id,
                }
                if allergens_str:
                    rec["allergens"] = allergens_str
                if label_names:
                    rec["labels"] = "; ".join(sorted(set(label_names)))
                if nutrients_raw:
                    rec.update(nutrients_raw)
                all_records.append(rec)

    # Removed additional fallbacks for brevity

    return all_records


def crawl_honest() -> List[Dict]:
    print("Fetching Honest Burgers landing page...")
    home = fetch_html(BASE_START)
    guids = get_menu_guids(home)
    print(f"Found {len(guids)} menu GUIDs")

    all_records: List[Dict] = []
    if not guids:
        # Many Ten Kites instances also render a default menu if no mguid is chosen
        # Attempt to parse the landing page directly as a fallback
        print("No GUIDs found; parsing landing page as single menu")
        all_records.extend(parse_menu_page(home))
        return all_records

    for g in guids:
        recs_for_guid: List[Dict] = []
        last_html: Optional[str] = None
        # Try plain HTTP on each candidate URL
        for build in CANDIDATE_MENU_URLS:
            url = build(g)
            try:
                html_text = fetch_html(url)
                last_html = html_text
                recs_for_candidate = parse_menu_page(html_text)
                if recs_for_candidate:
                    recs_for_guid = recs_for_candidate
                    print(f" - {len(recs_for_guid)} items from mguid {g} via {url}")
                    break
            except Exception as e:
                print(f"Failed to fetch mguid {g} via {url}: {e}")
                continue
        if not recs_for_guid:
            print(f" - 0 items from mguid {g} across {len(CANDIDATE_MENU_URLS)} candidate URL(s)")
            # Dump last HTML for troubleshooting
            try:
                dump_path = os.path.join(path_out, f"debug_mguid_{g[:8]}.html")
                if last_html:
                    with open(dump_path, "w") as f:
                        f.write(last_html)
                    print(f"   [debug] saved last fetched HTML to {dump_path}")
            except Exception as e:
                print(f"   [debug] failed to write debug HTML: {e}")
        all_records.extend(recs_for_guid)

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
    data = crawl_honest()
    print(f"Total items scraped: {len(data)}")
    save_outputs(data)
