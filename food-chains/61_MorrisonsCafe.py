import os
from datetime import date
import pandas as pd
import requests
from define_collection_wave import folder
from helpers import headers, create_folder

# collect the menu for the London Peckham location at 12pm

# Outputs
path_out = create_folder('61_MorrisonsCafe', folder)
file_json = os.path.join(path_out, 'morrisons_cafe_items.json')
file_jsonl = os.path.join(path_out, 'morrisons_cafe_items_JSONL.json')
file_csv = os.path.join(path_out, 'morrisons_cafe_items.csv')

location = '306EI'
time_slot = '12:00'

url_category = f'https://www.morrisons.com/cafe/menudata/{location}/Category/0?timeSlot={time_slot}&firstCall=true'
print('url_category', url_category)
categories = requests.get(url_category, headers=headers).json()

items = []
for category in categories.get('categories'):
    cat_id = category.get('categoryId')
    cat_url = f'https://www.morrisons.com/cafe/menudata/306EI/Category/{cat_id}?timeSlot={time_slot}'
    print('cat_url', cat_url)
    cat_data = requests.get(cat_url, headers=headers).json()
    cat_name = cat_data.get('categoryTitle')
    try:
        menu_items = cat_data.get('menuItems')
    except:
        menu_items = []
    if menu_items is None:
        menu_items = []
    for menu_item in menu_items:
        item_dict = {
            'collection_date': date.today().strftime("%b-%d-%Y"),
            'rest_name': 'Morrisons Cafe',
            'menu_section': cat_name,
            'item_name': menu_item.get('menuItemName'),
            'item_id': menu_item.get('menuItemId'),
            'price': menu_item.get('menuItemBasePrice'),
            'kcal': menu_item.get('kcal')
        }
        items.append(item_dict)

items_df = pd.DataFrame(items)
items_df.to_csv(file_csv, index=False)
items_df.to_json(file_json, orient='records')
items_df.to_json(file_jsonl, orient='records', lines=True)
print(f'Scraped {len(items)} items.')
print(f'Saved: {file_json}')
print(f'Saved: {file_jsonl}')
print(f'Saved: {file_csv}')