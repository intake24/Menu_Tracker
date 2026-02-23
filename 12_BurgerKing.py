import json
import urllib.parse
import requests
from datetime import date
import pandas as pd


from define_collection_wave import folder
from helpers import create_folder, clean_text

file_burgerking_csv = create_folder('12_BurgerKing', folder)
file_burgerking_json = file_burgerking_csv + '/burgerking_nutrition.json'
file_burgerking_csv = file_burgerking_csv + '/burgerking_nutrition.csv'

# Sanity GROQ API (GraphQL schema changed; nutrition explorer widget type no longer in schema)
SANITY_GROQ_BASE = 'https://czqk28jt.apicdn.sanity.io/v2023-08-01/data/query/prod_bk_gb'
STATIC_PAGE_ID = 'a180e7eb-948b-44d0-adca-187b413b14f1'


def _fetch_menu_via_groq():
    """Fetch nutrition explorer menu via Sanity GROQ (avoids broken GraphQL union)."""
    query = (
        '*[_id == $pageId][0]{'
        ' "menu": widgets[_type == "nutritionExplorerWidget"][0].menu->{'
        '  "options": options[]->{'
        '   "name": name.en,'
        '   "options": options[]->{'
        '    _id, _type, "name": name.en,'
        '    "nutrition": coalesce(nutritionWithModifiers, nutrition),'
        '    "allergens": allergens,'
        '    "mainItem": mainItem->{ "name": name.en, nutrition, nutritionWithModifiers, allergens }'
        '   }'
        '  }'
        ' }'
        '}'
    )
    url = '{}?query={}&$pageId={}'.format(
        SANITY_GROQ_BASE, urllib.parse.quote(query), urllib.parse.quote(json.dumps(STATIC_PAGE_ID))
    )
    headers = {
        'accept': '*/*',
        'origin': 'https://www.burgerking.co.uk',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36',
    }
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if 'error' in data:
        raise RuntimeError(data['error'])
    return data.get('result', {})


def _items_from_section(section):
    """Yield (name, nutrition_dict, allergens_list) from a section options array."""
    for opt in section.get('options') or []:
        if not isinstance(opt, dict):
            continue
        name = opt.get('name') or opt.get('_id') or 'Unknown'
        if isinstance(name, dict):
            name = name.get('en', 'Unknown')
        nutrition = opt.get('nutrition')
        allergens = opt.get('allergens')
        if nutrition is None and opt.get('mainItem'):
            main = opt['mainItem']
            nutrition = main.get('nutritionWithModifiers') or main.get('nutrition')
            if allergens is None:
                allergens = main.get('allergens')
        if nutrition is None:
            continue
        nutrition_data = {k: v for k, v in nutrition.items()
                         if v is not None and not isinstance(v, str) and k != '_type'}
        allergen_list = []
        if isinstance(allergens, dict):
            allergen_list = [k for k, v in allergens.items()
                             if v and not isinstance(v, str) and (v > 0 if isinstance(v, (int, float)) else True)]
        yield name, nutrition_data, allergen_list


def crawl_burgerking_nutrition():
    """Crawl Burger King nutrition data using Sanity GROQ API (GraphQL schema no longer exposes nutrition explorer)."""
    try:
        print("Making request to Burger King (Sanity GROQ) API...")
        result = _fetch_menu_via_groq()
        menu = result.get('menu') or {}
        menu_options = menu.get('options') or []

        if not menu_options:
            print("Error extracting menu data: no menu options found.")
            debug_path = file_burgerking_json.rsplit('/', 1)[0] + '/burgerking_api_response_debug.json'
            try:
                with open(debug_path, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"Raw response saved to {debug_path}")
            except Exception as save_err:
                print(f"Could not save debug file: {save_err}")
            return

        results = []
        total_items = 0

        for category in menu_options:
            try:
                category_name = clean_text(category.get('name') or 'Unknown Category')
                if isinstance(category_name, dict):
                    category_name = clean_text(category_name.get('en', 'Unknown Category'))
                print(f"Processing category: {category_name}")

                for product_name, nutrition_data, allergen_list in _items_from_section(category):
                    try:
                        product_name = clean_text(product_name)
                        item_dict = {
                            'rest_name': 'Burger King',
                            'collection_date': date.today().strftime("%b-%d-%Y"),
                            'category_name': category_name,
                            'product_name': product_name,
                            'allergens': allergen_list,
                        }
                        if nutrition_data:
                            item_dict.update(nutrition_data)
                        results.append(item_dict)
                        total_items += 1
                    except Exception as e:
                        print(f"Error processing product '{product_name}': {str(e)}")
                        continue
            except Exception as e:
                print(f"Error processing category: {str(e)}")
                continue

        print("API response received successfully")
        with open(file_burgerking_json, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Scraped {total_items} items from {len(menu_options)} categories. Data saved to {file_burgerking_json}.")

        if results:
            df = pd.DataFrame(results)
            df.to_csv(file_burgerking_csv, index=False)
            print(f"Data also saved to CSV: {file_burgerking_csv}")
        else:
            print("No data to save to CSV")

    except requests.RequestException as e:
        print(f"Error making API request: {str(e)}")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")


if __name__ == '__main__':
    crawl_burgerking_nutrition()
