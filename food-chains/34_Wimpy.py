import json
import os
from datetime import date
from typing import Dict, List, Optional

import requests
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder

BASE_URL = "https://wimpy.uk.com/api/menu-dish/"
REST_NAME = "Wimpy"
MAX_ID = 500  # mirrors the original Scrapy spider range(500)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

# Outputs
path_out = create_folder("34_Wimpy", folder)
file_json = os.path.join(path_out, "wimpy_items.json")
file_csv = os.path.join(path_out, "wimpy_items.csv")


def fetch_dish(id_: int) -> Optional[Dict]:
    url = f"{BASE_URL}{id_}"
    try:
        print(f"Requesting {url}")
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


def val(dct: Optional[Dict], *keys) -> Optional[str]:
    cur = dct
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def build_record(id_: int, data: Dict) -> Dict:
    nutr = data.get("nutritionals", {}) or {}
    return {
        "collection_date": date.today().strftime("%b-%d-%Y"),
        "rest_name": REST_NAME,
        "item_id": str(id_),
        "item_name": data.get("name"),
        "item_description": data.get("description"),
        "carb": val(nutr, "CARBOHYDRATE", "values", "PORTION"),
        "carb_100": val(nutr, "CARBOHYDRATE", "values", "100G"),
        "kj": val(nutr, "ENERGY_KJ", "values", "PORTION"),
        "kj_100": val(nutr, "ENERGY_KJ", "values", "100G"),
        "kcal": val(nutr, "ENERGY_KCAL", "values", "PORTION"),
        "kcal_100": val(nutr, "ENERGY_KCAL", "values", "100G"),
        "fat": val(nutr, "FAT", "values", "PORTION"),
        "fat_100": val(nutr, "FAT", "values", "100G"),
        "fibre": val(nutr, "FIBRE", "values", "PORTION"),
        "fibre_100": val(nutr, "FIBRE", "values", "100G"),
        "protein": val(nutr, "PROTEIN", "values", "PORTION"),
        "protein_100": val(nutr, "PROTEIN", "values", "100G"),
        "salt": val(nutr, "SALT", "values", "PORTION"),
        "salt_100": val(nutr, "SALT", "values", "100G"),
        "sugar": val(nutr, "SUGAR", "values", "PORTION"),
        "sugar_100": val(nutr, "SUGAR", "values", "100G"),
        "satfat": val(nutr, "SATURATE", "values", "PORTION"),
        "satfat_100": val(nutr, "SATURATE", "values", "100G"),
        "allergens": data.get("allergens"),
        "source_url": f"{BASE_URL}{id_}",
    }


def crawl_wimpy(max_id: int = MAX_ID) -> List[Dict]:
    records: List[Dict] = []
    missing = 0
    for i in range(max_id):
        data = fetch_dish(i)
        if not data:
            missing += 1
            continue
        try:
            rec = build_record(i, data)
            records.append(rec)
        except Exception as e:
            # keep parity with original spider's permissive error handling
            print(f"Error parsing id {i}: {e}")
    print(f"Fetched {len(records)} dishes, {missing} missing or invalid.")
    return records


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
    data = crawl_wimpy()
    save_outputs(data)
