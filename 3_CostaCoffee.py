import json
import logging
import re
from time import sleep
import requests
import os
import pandas as pd

from define_collection_wave import folder
from helpers import create_folder
path_out = create_folder('3_CostaCoffee', folder)
file_json = path_out + '/costacoffee_nutrition.json'
file_csv = path_out + '/costacoffee_nutrition.csv'
REST_NAME = "CostaCoffee"

logger = logging.getLogger(__name__)

headers = {
    'accept': 'application/json, text/plain, */*',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/json',
    # 'cookie': '_ga=GA1.1.1356748925.1732331838; ak_bmsc=095BADF0A5EBE37BA229D6CC70280A93~000000000000000000000000000000~YAAQiHAsMaXEsjGTAQAAdCYGVxkV4jkjhcKytLA+o9s3JJlCe8G9MbZKpKTKsHDuBz7OcZ2O+TU+z1RDS8cBSk/ezNSEq2Ig8y8eZLDqvSX1PXn26MinP1+cKLYVOwKRIle5JwdeOZWexslrTP4O0eSlwnJDneD28XiDtiKY8rHbT3uSa7kuAxyD6hIAWPHN7g/8iR5lneki2wF2Uj0KkNtH0JRKZ3d6myjtkFyXPpi8ICetSv7SKKJb97J5m7bonzttuZSsTzwP3CXmDk9ZVHlFpp+nURpk35HldNgxjtN61BrXObZNYz5vSX9aWqzjZvl25xsFWiyuy9Aq/YouYJkpiQsZWS1c3BPZ5lRbuMfnefs4f746AJc9NBZSVVMfVTtpFae5mMCcAikHQz8O3rEpNS9xjT+ZgUo1CCckVxsf1RavH3ZUvRKi/bXQaFH2m8dfvsxZfFR1aKBEPofV; OptanonAlertBoxClosed=2024-11-23T03:17:23.971Z; at_check=true; AMCVS_30304ADC5B7680930A495EDE%40AdobeOrg=1; _hjSessionUser_2519238=eyJpZCI6IjNkMDk0NDIxLTNiMDctNWZhZi1iYThjLWE3NmI1NzEyNjliMyIsImNyZWF0ZWQiOjE3MzIzMzE4NDQ3MTIsImV4aXN0aW5nIjp0cnVlfQ==; s_cc=true; AMCV_30304ADC5B7680930A495EDE%40AdobeOrg=-1124106680%7CMCIDTS%7C20051%7CMCMID%7C14647688899982618531862131468614419081%7CMCAAMLH-1732936644%7C12%7CMCAAMB-1732936644%7CRKhpRz8krg2tLO6pguXWp5olkAcUniQYPHaMWWgdJ3xzPWQmdj0y%7CMCOPTOUT-1732339044s%7CNONE%7CMCAID%7CNONE%7CMCSYNCSOP%7C411-20058%7CvVersion%7C5.2.0; _abck=296BD6DE0A847932D50EEF0697B33FEE~0~YAAQiHAsMe/UsjGTAQAASlYHVwzCyqvdLDl78vMwcZ98Lapwj7WbHYQsjDlwLTNfz13DUIiea4VCaBtpuhSMjts9dEfLD8WXUzz7lcED56KqyQbeZubE/efwSFzWVj2ggnjVShxCo40qv3zfBO0ohxvFLbo6in5Q+T7K2vrufT2wrAaiE2kUIGC6ajr8WpBoqNKyOqw/vpGinWXgk1vhVf85kpziI0zM+0ocxW16iEurkOulTRpwrFROgbhTlVE1ECyuLLXCUQTrjDm8gadpNs5mYXMn8mKklZcfxeFAIVV4pvpj6I/DM9CSq1L0zaMSKNjUYpP+d2xUpt1E+MpBui/MN5Vu9NNdbxXKnxbeCxEtjHQ1Uo/zLFv7tSnk5l9J78IvqufqkENyvEb6E4wPHCeRbUYrqj/rAhWI6LS4mGTcdrmJR7405xd1J52VrL0nQlQNWQWekZrHUx13IY6+UT2+mU87I/N1kkUEJGI3EcJm~-1~-1~-1; _hjSession_2519238=eyJpZCI6IjZiMDlmNmU2LTI1MmEtNGYzMy05MjNkLTYzNzMyODY0ODM1MCIsImMiOjE3MzIzMzc4NzQ4NjMsInMiOjEsInIiOjEsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MH0=; bm_sz=0F7DE667EA7A2261D814A2B02AEF9FA3~YAAQp4osMUvH6jSTAQAA/LxiVxmw9KWmqnop/dMBJK8m/tMjolupdtV9iXLrDN+NzT/z+ohn0wTLqyvGFDqUbePGMa6JqHDwRVl8OBg/3eaJ0dlsbVVdJFowTLuYl8alO8Hhn3wBdQLd9dG6VID5bNUaMZa9lPpfuzriP4+CWSmHZba6UcAglOpFV+beV+7X0OCcdfHUxQ+1JfL6m/D5I5ZEc+/z/Z74+FMczptqUjGyGMaMfkKH2Q+Tdy4wJo2QDrNcoCqrCnZ0FDxiwq4qK/L9bEAlc/Do6K4kBrSeNM5DDZSJY7umetbTwot3FXqu5Awr4OWvW9P7NJe+DCltYkaeJRuTFOCBwHGHb3s825w7vLM3kJcxHX11KRp+04afitvhBzhaBrOFJS6BXPB237aUrO9wnobUi3JKD+03t0Kcbw==~3618870~3551557; OptanonConsent=isIABGlobal=false&datestamp=Sat+Nov+23+2024+10%3A28%3A30+GMT%2B0530+(India+Standard+Time)&version=6.34.0&hosts=&consentId=070bdb76-c21e-4823-90fc-072f15b9212c&interactionCount=1&landingPath=NotLandingPage&groups=C0001%3A1%2CC0002%3A1%2CC0003%3A1%2CC0004%3A1&geolocation=IN%3BGJ&AwaitingReconsent=false; _ga_Q2ESTRQHQ0=GS1.1.1732337908.2.1.1732337910.0.0.0; mbox=PC#9c6e497a98e14e588d85c09cb6582f30.41_0#1795582711|session#2f050511653f48d2815248050feb106e#1732339758; s_sq=%5B%5BB%5D%5D; bm_sv=FBF2080EA7FA9ABD41BE4612A49B0BDE~YAAQp4osMQ/J6jSTAQAATsViVxnWZ1oFcFDYsTwkJXYnEWWorJas/FhHsmCpkB7eRGWLD1OFyYo7xUOQLQDG1npj7p80K95NPtffX73XNdf+hU2Tu8jZJnJpxkpHspyp+CuYqS9MT5hmzoikWUsM8+WqSRWHsmcvI/4YvuhyBFGvLkHnpaTIUDvQeZH2Dt9qdAmkuapZTFGq1LD3+x86stOPJPt0HF41zt8PC8FqpHtVa9iWOzBgKzIpt2k+xr0o9JM=~1',
    'origin': 'https://www.costa.co.uk',
    'priority': 'u=1, i',
    'referer': 'https://www.costa.co.uk/menu',
    'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'x-channel': 'web',
}

json_datas = [
{
    'query': '\n  query MasterProduct {\n    masterProducts(groupCodes: ["MP-0002247","MP-0002246","MP-0002274","Gingerbread & Cream Latte","Latte","Cappuccino","Americano","Flat White","Mocha","Espresso","Cortado","Mocha Cortado","Terry\'s Orange Hot Chocolate","Black Forest Hot Chocolate","MP-0002248","Hot Chocolate","White Hot Chocolate","Chai Latte","MP-0000662","MP-0002245","Tropical Mango Bubble Frappé","Strawberries & Cream Frappé","Salted Caramel Frappé","Salted Caramel Frappé with Coffee","Chocolate Fudge Brownie Frappé","Chocolate Fudge Brownie Frappé Mocha","Coffee Frappé","MP-0002260","MP-0002261","MP-0002279","MP-0000463","Iced Latte","Iced Americano Black","MP-0000701","Iced Flat White","Iced Mocha","MP-0000704","MP-0001671","English Breakfast Tea","Decaf Tea","Earl Grey Tea","Green Tea","Mint Tea","Superfruity Infusion","Citrus Zing with Vitamin C","Spiced Apple with Vitamin B6","Mellow Mango with Zinc","Mango & Passion Fruit","Red Summer Berries"], effectiveFromDate: null){\n      items {\n        id\n        brandName\n        productDisplayName\n        productDescription\n        productCode\n        groupCode\n        images {\n          imageStyle\n          imageUrl\n        }\n        variations {\n            variationCategoryName\n            variationName\n        }\n        nutritionProducts {\n          id\n          productCode\n          effectiveFromDate\n          ingredients\n          variations {\n            coffeeType\n            milkSuffix\n            milkType\n            serviceDelivery\n            size\n          }\n          dietaryChoices {\n            suitableForVegetarians\n            suitableForVegans\n          }\n          allergens {\n            celery\n            cereals {\n              wheat\n              rye\n              barley\n              oat\n            }\n            crustacean\n            egg\n            fish\n            lupin\n            milk\n            mollusc\n            mustard\n            peanut\n            sesame\n            soya\n            sulphite\n            treeNuts\n            treeNutSource\n          }\n          nutritionPer100g {\n            carbohydrates\n            energykCal\n            energykJ\n            fat\n            fibre\n            protein\n            salt\n            saturates\n            sugars\n            vitaminB6\n            vitaminB12\n            vitaminC\n            zinc\n          }\n          nutritionPerPortion {\n            portionWeight\n            carbohydrates\n            energykCal\n            energykJ\n            fat\n            fibre\n            protein\n            salt\n            saturates\n            sugars\n            vitaminB6\n            vitaminB12\n            vitaminC\n            zinc\n            portionWeight\n          }\n        }\n      }\n    }\n  }\n',
    'vars': {},
},
{
    'query': '\n  query MasterProduct {\n    masterProducts(groupCodes: ["MP-0002244","British Pork Sausage Bap","British Smoked Bacon Bap","Egg Mushroom & Spinach Bap (V)","MP-0001610","Greek Yogurt with Mixed Berry Compote & Granola","MP-0001669","Wholegrain Porridge New","Seeded Brown Toast","White Toast","Wholegrain Porridge","MP-0000590","MP-0002234","MP-0001114","MP-0001640","MP-0002226","MP-0002227","Turkey Feast Sandwich","MP-0001608","MP-0000996","Wiltshire Ham & Mature Cheddar Toastie","Cheese & Tomato Toastie","Tuna Melt Panini","Mozzarella & Tomato Panini","MP-0001271","MP-0001161","Ham & Cheese Toastie","MP-0001663","MP-0000447","MP-0002148","MP-0001087","MP-0001086","Free Range Egg Mayo Sandwich Without Cress","Mac & Cheese","MP-0001668","MP-0002276","All Butter Mince Pie","Terry’s Chocolate Orange Muffin","MP-0001681","MP-0002229","MP-0002278","Carrot & Walnut Cake","MP-0002275","MP-0002277","MP-0002196","MP-0002280","Croissant","Almond Croissant (V)","Lotus Biscoff Cheezecake (Vg)","MP-0002289","MP-0002290","Chocolate Twist","MP-0000518","Fruited Teacake (Vg)","Blueberry Muffin","Lemon Muffin","MP-0000543","Cinnamon Bun","Millionaire\'s Shortbread","Chocolate Tiffin","Raspberry & Almond Bake","Bakewell Tart","Lemon Curd Tart","MP-0000490","MP-0002198","MP-0002199","MP-0002200","MP-0002201","Triple Belgian Chocolate Biscuits","Stem Ginger Biscuits","Fruit & Oat Biscuits","Millionaire’s Shortbread Bar (GF)","Mince Tart (GF v)","Costa Milk Choc Chunks Gluten Free Brownie","Fruity Flapjack (GF v)","Jammy Shortbread Biscuits","Mini Shortbread Bites","Caramel Waffles"], effectiveFromDate: null){\n      items {\n        id\n        brandName\n        productDisplayName\n        productDescription\n        productCode\n        groupCode\n        images {\n          imageStyle\n          imageUrl\n        }\n        variations {\n            variationCategoryName\n            variationName\n        }\n        nutritionProducts {\n          id\n          productCode\n          effectiveFromDate\n          ingredients\n          variations {\n            coffeeType\n            milkSuffix\n            milkType\n            serviceDelivery\n            size\n          }\n          dietaryChoices {\n            suitableForVegetarians\n            suitableForVegans\n          }\n          allergens {\n            celery\n            cereals {\n              wheat\n              rye\n              barley\n              oat\n            }\n            crustacean\n            egg\n            fish\n            lupin\n            milk\n            mollusc\n            mustard\n            peanut\n            sesame\n            soya\n            sulphite\n            treeNuts\n            treeNutSource\n          }\n          nutritionPer100g {\n            carbohydrates\n            energykCal\n            energykJ\n            fat\n            fibre\n            protein\n            salt\n            saturates\n            sugars\n            vitaminB6\n            vitaminB12\n            vitaminC\n            zinc\n          }\n          nutritionPerPortion {\n            portionWeight\n            carbohydrates\n            energykCal\n            energykJ\n            fat\n            fibre\n            protein\n            salt\n            saturates\n            sugars\n            vitaminB6\n            vitaminB12\n            vitaminC\n            zinc\n            portionWeight\n          }\n        }\n      }\n    }\n  }\n',
    'vars': {},
}
]
logging.info(f"Total JSON payloads to process: {len(json_datas)}")

for f_idx, json_data in enumerate(json_datas):
    if f_idx % 10 == 0:
        logger.info(f"Processing {f_idx+1}/{len(json_datas)}")
    response = requests.post('https://www.costa.co.uk/api/mdm/',  headers=headers, json=json_data)
    js = json.loads(response.text)

    all_items = js['data']['masterProducts']['items']
    logging.info(f"Total items found in payload {f_idx+1}: {len(all_items)}")

    for i_idx, all_item in enumerate(all_items):
        product_name = all_item.get('productDisplayName','')
        if product_name:
            product_name = product_name.strip()
        # print(product_name)
        if i_idx % 10 == 0:
            logger.info(f"  Processing item {i_idx+1}/{len(all_items)}, Product Name: {product_name}")
        if not product_name:
            continue
        product_description = all_item.get('productDescription', '')
        if product_description:
            product_description = product_description.replace("\n",'').strip()
        all_nutritions = all_item.get('nutritionProducts','')
        if all_nutritions:
            for all_nutrition in all_nutritions:
                size = all_nutrition.get('variations','').get('size','')
                milkType = all_nutrition.get('variations','').get('milkType','')
                coffeeType = all_nutrition.get('variations','').get('coffeeType','')

                try:
                    nutritionPer100g = {f"{k}_Per 100g/ml": v for k, v in all_nutrition['nutritionPer100g'].items()}
                except:
                    nutritionPer100g = ''
                if not nutritionPer100g:
                    nutritionPer100g = ''

                try:
                    nutritionPerPortion = {f"{k}_Per Portion": v for k, v in all_nutrition['nutritionPerPortion'].items() if k != 'portionWeight'}
                except:
                    nutritionPerPortion = ''
                if not nutritionPerPortion:
                    nutritionPerPortion = ''

                try:
                    allergens = {f"{k}": '' if v in ['No',' '] else v  for k,v in all_nutrition['allergens'].items() if isinstance(v,str)}
                except:
                    allergens = ''
                if not allergens:
                    allergens = ''

                ingredients = all_nutrition.get('ingredients','')
                if not ingredients:
                    ingredients = ''

                data = {
                    'Product_Name': product_name,
                    'Product_Description': product_description,
                    'Size': size,
                    'Milk': milkType,
                    'CoffeeType': coffeeType,
                    'Ingredients': ingredients,
                }

                data.update(nutritionPer100g)
                data.update(nutritionPerPortion)
                data.update(allergens)

df = pd.DataFrame([data])
if os.path.exists(file_csv):
    df.to_csv(file_csv, header=False, index=False, mode='a')
    logger.info("Data saved to CSV: %s", file_csv)
else:
    df.to_csv(file_csv, header=True, index=False, mode='a')
    logger.info("Data saved to CSV: %s", file_csv)



































