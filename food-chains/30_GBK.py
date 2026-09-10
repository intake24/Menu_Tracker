import json

from datetime import date
import requests
from lxml import html
import  pandas as pd
import os

from define_collection_wave import folder
from helpers import create_folder
path_GBK = create_folder('30_GBK', folder)

headers = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9,en-IN;q=0.8',
    'priority': 'u=1, i',
    'referer': 'https://menus.tenkites.com/brg/gourmetburgerkitchen',
    'sec-ch-ua': '"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36 Edg/130.0.0.0',
}

params = {
    'cl': 'true',
    'mguid': '7608dd93-f3d4-49a5-9c1f-e58cee5e6f9b',
    'clmob': 'true',
}

data_store = []

all_keys = set()



base_url = 'https://menus.tenkites.com//brg/gourmetburgerkitchen'
category_response = requests.get(base_url,headers=headers)
sc = html.fromstring(category_response.text)
categories = sc.xpath("//div[contains(@class,'k10-menu-selector__option')]/div/@data-menu-identifier")
for category in categories:

    params['mguid'] = category
    response = requests.get('https://menus.tenkites.com/brg/gourmetburgerkitchen',params = params, headers=headers)
    sc = html.fromstring(response.text)
    json_request = sc.xpath("//script[@type='application/ld+json'][2]/text()")[0]
    json_response = json.loads(json_request)
    menu_name = json_response['name']
    print(menu_name)
    each_menu_section_products = json_response['hasMenuSection']
    for each_menu_section_product in each_menu_section_products:

        item_category_name = each_menu_section_product['name']
        all_items = each_menu_section_product['hasMenuItem']
        if not isinstance(all_items,list):
            all_items = [all_items]
            # for item in all_items:
            #     try:
            #         item_name = item['name']
            #     except:
            #         item_name = ''
            #     try:
            #         item_description = item['description']
            #     except:
            #         item_description = ''
            #     try:
            #         price = item['offers']['price']
            #     except:
            #         price = ''
            #     try:
            #         nutrition = item['nutrition']
            #     except:
            #         nutrition = ''
            #     data = {
            #         'collection_date': date.today().strftime("%b-%d-%Y"),
            #         'rest_name': "GBK",
            #         'menu_name': menu_name,
            #         'item_category_name': item_category_name,
            #         'item_name': item_name,
            #         'item_description': item_description,
            #         'price': price,
            #         'nutrition': nutrition
            #     }
            #     df = pd.DataFrame([data])
            #     if os.path.exists('30_GBK_NOV_08_2024/30_GBK.csv'):
            #         df.to_csv('30_GBK.csv', header=False, index=False, mode='a')
            #     else:
            #         df.to_csv('30_GBK.csv', header=True, index=False, mode='a')
        for item in all_items:
            try:
                item_name = item['name']
            except:
                item_name = ''
            try:
                item_description = item['description']
            except:
                item_description = ''
            try:
                price = item['offers']['price']
            except:
                price = ''
            try:
                nutrition = item['nutrition']
            except:
                nutrition = ''
            if nutrition:
                if '@type' in nutrition:
                    del nutrition['@type']

            data = {
                'collection_date': date.today().strftime("%b-%d-%Y"),
                'rest_name': "GBK",
                'menu_name': menu_name,
                'item_category_name': item_category_name,
                'item_name': item_name,
                'item_description': item_description,
                'price': price,
            }
            all_keys.update(nutrition.keys())

            ne = {key : nutrition.get(key,None) for key in all_keys}

            data.update(ne)

            data_store.append(data)


for entry in data_store:
    for key in all_keys:
        if key not in entry:
            entry[key] = None

df = pd.DataFrame(data_store)
with open(path_GBK + '/30_GBK_items.json', 'w') as file:
    json.dump(data_store, file, indent=2)
df.to_csv(path_GBK + '/30_GBK_items.csv', index=False)
print(f"Scraped {len(data_store)} items. Data saved to {path_GBK}.")
