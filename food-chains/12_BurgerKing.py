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
# Website menu (https://www.burgerking.co.uk/menu) – full section list including FLAME-GRILLED with 14 pickers
WEBSITE_MENU_ID = '9670fe1e-0342-41b7-9f92-a8fb1907120f'


def _fetch_website_menu_via_groq():
    """Fetch menu as shown on https://www.burgerking.co.uk/menu (same structure: sections -> pickers -> items)."""
    query = (
        '*[_id == $menuId][0]{'
        ' "options": options[]->{'
        '  _id, _type, "name": name.en,'
        '  "options": options[]->{'
        '   _id, _type, "name": name.en,'
        '   "items": options[].option->{'
        '    _id, _type, "name": name.en,'
        '    "nutrition": coalesce(nutritionWithModifiers, nutrition),'
        '    "allergens": allergens,'
        '    "mainItem": mainItem->{ "name": name.en, nutrition, nutritionWithModifiers, allergens }'
        '   }'
        '  }'
        ' }'
        '}'
    )
    url = '{}?query={}&$menuId={}'.format(
        SANITY_GROQ_BASE, urllib.parse.quote(query), urllib.parse.quote(json.dumps(WEBSITE_MENU_ID))
    )
    headers = {
        'accept': '*/*',
        'origin': 'https://www.burgerking.co.uk',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36',
    }
    resp = requests.get(url, headers=headers, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    if 'error' in data:
        raise RuntimeError(data['error'])
    return data.get('result', {})


def _fetch_menu_via_groq():
    """Fetch nutrition explorer menu via Sanity GROQ (avoids broken GraphQL union)."""
    # Menu has options[] = refs to Section. Section has options[] = refs to Picker. Picker has options[].option = refs to Item.
    # We expand: section.options[]-> (Pickers) and picker.options[].option-> (Items).
    query = (
        '*[_id == $pageId][0]{'
        ' "menu": widgets[_type == "nutritionExplorerWidget"][0].menu->{'
        '  "options": options[]->{'
        '   _id, _type, "name": name.en,'
        '   "options": options[]->{'
        '    _id, _type, "name": name.en,'
        '    "items": options[].option->{'
        '     _id, _type, "name": name.en,'
        '     "nutrition": coalesce(nutritionWithModifiers, nutrition),'
        '     "allergens": allergens,'
        '     "mainItem": mainItem->{ "name": name.en, nutrition, nutritionWithModifiers, allergens }'
        '    }'
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


def _fetch_supplemental_pickers():
    """Fetch Pickers not in the nutrition explorer sections (e.g. WHOPPER with Bacon and Cheese) so we include all menu variants."""
    # Pickers that look like menu product groups (exclude offers/prizes in Python)
    query = (
        '*[_type == "picker" && name.en match "*Bacon*"]{'
        ' "name": name.en,'
        ' "items": options[].option->{'
        '  _id, _type, "name": name.en,'
        '  "nutrition": coalesce(nutritionWithModifiers, nutrition),'
        '  "allergens": allergens,'
        '  "mainItem": mainItem->{ "name": name.en, nutrition, nutritionWithModifiers, allergens }'
        ' }'
        '}'
    )
    url = '{}?query={}'.format(SANITY_GROQ_BASE, urllib.parse.quote(query))
    headers = {
        'accept': '*/*',
        'origin': 'https://www.burgerking.co.uk',
        'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36',
    }
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if 'error' in data:
        return []
    # Exclude offer/prize pickers (e.g. "Offer - ...", "£5.99 ...", "EASTER EGG")
    exclude_prefixes = ('Offer', 'Prize', 'EASTER', 'Scratch', '£', 'Free ', 'Reward')
    pickers = data.get('result', [])
    return [
        p for p in pickers
        if isinstance(p, dict) and isinstance(p.get('name'), str)
        and not p.get('name', '').startswith(exclude_prefixes)
    ]


def _items_from_section(section):
    """Yield (name, nutrition_dict, allergens_list) from a section.
    Section has options = list of Picker (with .items) or direct Item/Combo (with .nutrition).
    """
    for opt in section.get('options') or []:
        if not isinstance(opt, dict):
            continue
        # Picker: has "items" array (options[].option->)
        items = opt.get('items')
        if items:
            for it in items:
                if not isinstance(it, dict):
                    continue
                name, nutrition_data, allergen_list = _item_to_tuple(it)
                yield name, nutrition_data or {}, allergen_list
            continue
        # Direct Item/Combo (no "items")
        name, nutrition_data, allergen_list = _item_to_tuple(opt)
        if nutrition_data is None:
            continue
        yield name, nutrition_data, allergen_list


def _nutrition_has_values(nut):
    """True if nutrition dict has at least one numeric value (not just _type)."""
    if not nut or not isinstance(nut, dict):
        return False
    return any(
        v is not None and isinstance(v, (int, float))
        for k, v in nut.items()
        if k != '_type'
    )


def _item_to_tuple(item):
    """Extract (name, nutrition_dict or None, allergens_list) from an item or combo."""
    name = item.get('name') or item.get('_id') or 'Unknown'
    if isinstance(name, dict):
        name = name.get('en', 'Unknown')
    # API sometimes returns nutritionWithModifiers as empty {_type}; use first source that has numeric values
    nutrition = None
    for candidate in (item.get('nutrition'), item.get('nutritionWithModifiers')):
        if _nutrition_has_values(candidate):
            nutrition = candidate
            break
    if nutrition is None and item.get('mainItem'):
        main = item['mainItem']
        for candidate in (main.get('nutrition'), main.get('nutritionWithModifiers')):
            if _nutrition_has_values(candidate):
                nutrition = candidate
                break
    allergens = item.get('allergens')
    if allergens is None and item.get('mainItem'):
        allergens = item['mainItem'].get('allergens')
    if nutrition is None:
        return name, None, []
    nutrition_data = {k: v for k, v in nutrition.items()
                     if v is not None and not isinstance(v, str) and k != '_type'}
    allergen_list = []
    if isinstance(allergens, dict):
        allergen_list = [k for k, v in allergens.items()
                        if v and not isinstance(v, str) and (v > 0 if isinstance(v, (int, float)) else True)]
    return name, nutrition_data, allergen_list


def crawl_burgerking_nutrition():
    """Crawl Burger King nutrition data using Sanity GROQ API. Uses website menu (burgerking.co.uk/menu) for full burger list."""
    try:
        print("Making request to Burger King (Sanity GROQ) API...")
        # Prefer website menu – matches https://www.burgerking.co.uk/menu (more sections and pickers)
        result = _fetch_website_menu_via_groq()
        menu_options = result.get('options') or []
        if not menu_options:
            # Fallback to nutrition explorer static page
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

        # Supplemental: Pickers not in explorer sections (e.g. WHOPPER® with Bacon and Cheese Meal Large)
        seen = {(clean_text(c.get('category_name', '')), clean_text(c.get('product_name', ''))) for c in results}
        supplemental = _fetch_supplemental_pickers()
        added = 0
        for picker in supplemental:
            if not isinstance(picker, dict):
                continue
            category_name = picker.get('name') or 'FLAME-GRILLED BURGERS'
            if isinstance(category_name, dict):
                category_name = category_name.get('en', 'FLAME-GRILLED BURGERS')
            category_name = clean_text(category_name)
            for it in picker.get('items') or []:
                if not isinstance(it, dict):
                    continue
                name, nutrition_data, allergen_list = _item_to_tuple(it)
                product_name = clean_text(name)
                key = (category_name, product_name)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    item_dict = {
                        'rest_name': 'Burger King',
                        'collection_date': date.today().strftime("%b-%d-%Y"),
                        'category_name': category_name,
                        'product_name': product_name,
                        'allergens': allergen_list or [],
                    }
                    if nutrition_data:
                        item_dict.update(nutrition_data)
                    results.append(item_dict)
                    total_items += 1
                    added += 1
                except Exception as e:
                    print(f"Error processing supplemental product '{product_name}': {str(e)}")
        if added:
            print(f"Added {added} items from supplemental pickers (e.g. WHOPPER® with Bacon and Cheese).")

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
