import json
import os
import re
from datetime import date
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder, clean_text

BASE_URL = "https://www.paul-uk.com/"
REST_NAME = "PAUL"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Output paths
path_out = create_folder("33_Paul", folder)
file_json = os.path.join(path_out, "paul_items.json")
file_csv = os.path.join(path_out, "paul_items.csv")


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def get_category_links(home_html: str) -> List[str]:
    soup = BeautifulSoup(home_html, "html.parser")
    links = [
        urljoin(BASE_URL, a["href"].strip())
        for a in soup.select('nav a[href*="/order-online/"]')
        if a["href"].strip()
    ]
    return list(dict.fromkeys(links))


def get_product_links_and_next(page_html: str, page_url: str) -> (List[str], Optional[str]):
    soup = BeautifulSoup(page_html, "html.parser")
    product_urls: List[str] = []

    for a in soup.select(".product-item a[href]"):
        product_urls.append(urljoin(page_url, a["href"]))

    next_link = None
    next_a = soup.select_one("a.pages-item-next[href], a.action.next[href]")
    if next_a and next_a.get("href") and next_a.get("aria-disabled") != "true":
        next_link = urljoin(page_url, next_a["href"]) 

    # unique
    product_urls = list(dict.fromkeys(product_urls))
    return product_urls, next_link


def parse_nutrition_blocks(soup: BeautifulSoup) -> (Dict[str, str], Dict[str, str], Optional[List[str]]):
    """
    Returns: (nutrient_dict_per_serving, nutrient_dict_per_100g, serving_size_numbers)
    - per-serving labels/values are under the first div.nutritional-title.hide-desk followed by two ULs
    - per-100g labels/values are two sibling ULs with class 'hide-desk' (labels then values)
    """
    nutrient_dict_serving: Dict[str, str] = {}
    nutrient_dict_100: Dict[str, str] = {}
    servingsize_nums: Optional[List[str]] = None

    for details in soup.select("details"):
        summary = details.select_one("summary")
        if not summary or "nutritional information" not in summary.get_text(" ", strip=True).lower():
            continue
        rows = details.select("table tr")
        if len(rows) < 2:
            continue
        headers = [cell.get_text(" ", strip=True) for cell in rows[0].select("th, td")]
        if len(headers) < 3:
            continue
        servingsize_nums = re.findall(r"[0-9]+(?:[.,][0-9]+)?", headers[1])
        for row in rows[1:]:
            cells = [cell.get_text(" ", strip=True) for cell in row.select("th, td")]
            if len(cells) < 3 or not cells[0]:
                continue
            nutrient_dict_serving[cells[0]] = cells[1]
            nutrient_dict_100[f"{cells[0]}_100g"] = cells[2]
        return nutrient_dict_serving, nutrient_dict_100, servingsize_nums

    # Legacy serving-size block (title + 2 following ULs)
    title = soup.select_one("div.nutritional-title.hide-desk")
    if title:
        title_text = title.get_text(strip=True)
        servingsize_nums = re.findall(r"[0-9]+", title_text)
        ul1 = title.find_next_sibling("ul")
        ul2 = ul1.find_next_sibling("ul") if ul1 else None
        if ul1 and ul2:
            labels = [li.get_text(strip=True) for li in ul1.select("li")]
            values = [li.get_text(strip=True) for li in ul2.select("li")]
            for k, v in zip(labels, values):
                nutrient_dict_serving[k] = v

    # Per-100g block (first ul.hide-desk with labels + next sibling ul with values)
    labels_ul = soup.select_one("ul.hide-desk")
    if labels_ul:
        values_ul = labels_ul.find_next_sibling("ul")
        if values_ul:
            labels_100 = [li.get_text(strip=True) for li in labels_ul.select("li")]
            values_100 = [li.get_text(strip=True) for li in values_ul.select("li")]
            for k, v in zip(labels_100, values_100):
                nutrient_dict_100[f"{k}_100g"] = v

    return nutrient_dict_serving, nutrient_dict_100, servingsize_nums


def parse_allergens(soup: BeautifulSoup) -> Dict[str, str]:
    for details in soup.select("details"):
        summary = details.select_one("summary")
        if not summary or "allergens" not in summary.get_text(" ", strip=True).lower():
            continue
        allergens = [li.get_text(" ", strip=True) for li in details.select(".allergens-new li")]
        if allergens:
            return {"present": allergens}

    allergen_map: Dict[str, str] = {}
    container = soup.find("div", id="allergens.present")
    if not container:
        return allergen_map
    uls = container.find_all("ul", limit=2)
    if len(uls) == 2:
        names = [li.get_text(strip=True) for li in uls[0].select("li")]
        vals = [li.get_text(strip=True) for li in uls[1].select("li")]
        allergen_map = dict(zip(names, vals))
    return allergen_map


def parse_product(url: str) -> Optional[Dict]:
    try:
        html = fetch_html(url)
    except Exception as e:
        print(f"Failed to fetch product {url}: {e}")
        return None

    soup = BeautifulSoup(html, "html.parser")

    name = soup.select_one(".product-title, .page-title-wrapper h1, h1")
    desc = soup.select_one('[itemprop="description"]')
    price = soup.select_one("span.price")

    nutrient_serv, nutrient_100, servingsize = parse_nutrition_blocks(soup)
    allergens = parse_allergens(soup)

    item = {
        "collection_date": date.today().strftime("%b-%d-%Y"),
        "rest_name": REST_NAME,
        "item_name": clean_text(name.get_text(strip=True)) if name else None,
        "item_desc": clean_text(desc.get_text(strip=True)) if desc else None,
        "price": price.get_text(strip=True) if price else None,
        "allergen": allergens,
        "servingsize": servingsize,
        "source_url": url,
    }
    item.update(nutrient_serv)
    item.update(nutrient_100)
    return item


def crawl_paul() -> List[Dict]:
    records: List[Dict] = []
    seen_products: Set[str] = set()

    print("Fetching homepage...")
    home_html = fetch_html(BASE_URL)
    cat_links = get_category_links(home_html)
    print(f"Found {len(cat_links)} category links")

    for cat in cat_links:
        print(f"Category: {cat}")
        cur = cat
        seen_pages: Set[str] = set()
        while cur and cur not in seen_pages:
            seen_pages.add(cur)
            try:
                html = fetch_html(cur)
            except Exception as e:
                print(f"Failed to fetch category {cur}: {e}")
                break

            product_urls, next_page = get_product_links_and_next(html, cur)
            new_urls = [u for u in product_urls if u not in seen_products]
            print(f" - {len(new_urls)} new products on page")
            for purl in new_urls:
                seen_products.add(purl)
                item = parse_product(purl)
                if item:
                    records.append(item)
            cur = next_page
    return records


def save_outputs(items: List[Dict]):
    with open(file_json, "w") as f:
        json.dump(items, f, indent=2)
    try:
        df = pd.DataFrame(items)
        df.to_csv(file_csv, index=False)
    except Exception as e:
        print(f"CSV export failed: {e}")
    print(f"Saved: {file_json}")
    print(f"Saved: {file_csv}")


if __name__ == "__main__":
    data = crawl_paul()
    print(f"Total items scraped: {len(data)}")
    save_outputs(data)
