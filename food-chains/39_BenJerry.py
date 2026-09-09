import requests
from lxml import html
import pandas as pd
import os
from datetime import date

from define_collection_wave import folder
from helpers import create_folder

path_benjerry = create_folder('39_BenJerry', folder)


# Primary mobile-like headers (kept from original working script)
headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'en-US,en;q=0.9,en-IN;q=0.8',
    'cache-control': 'max-age=0',
    'priority': 'u=0, i',
    'sec-ch-ua': '"Chromium";v="130", "Microsoft Edge";v="130", "Not?A_Brand";v="99"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36 Edg/130.0.0.0',
}

base_url = 'https://www.benjerry.co.uk/flavours'

# Use a Session for connection reuse and cookie persistence
session = requests.Session()

# Fallback desktop headers (try when 403)
fallback_headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.9',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'accept-encoding': 'gzip, deflate, br',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'referer': 'https://www.benjerry.co.uk/',
    'sec-ch-ua': '"Chromium";v="125", "Not=A?Brand";v="24", "Google Chrome";v="125"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
}


def fetch(url: str) -> requests.Response:
    # Try desktop-like headers first (often passes bot checks better)
    print(f"Fetching: {url}")
    resp = session.get(url, headers=fallback_headers, timeout=10)
    if resp.status_code == 403:
        # Retry with original mobile-like headers
        print(f"Retrying with mobile headers: {url}")
        resp = session.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp


# Collect all records first
data_store = []

# Warm up session to establish cookies
try:
    print("Warming up session...")
    _ = session.get('https://www.benjerry.co.uk/', headers=fallback_headers, timeout=10)
except Exception as e:
    print(f"Warning: homepage warm-up failed: {e}")

# Fetch base page and extract category links
# Ensure referer points to homepage
fallback_headers['referer'] = 'https://www.benjerry.co.uk/'
print("Fetching base page...")
response = fetch(base_url)
sc = html.fromstring(response.text)

all_categories_links = sc.xpath("//section//a[contains(text(),'View All')]/@href")

for all_category_link in all_categories_links:
    category_url = 'https://www.benjerry.co.uk' + all_category_link
    try:
        print(f"Fetching category: {category_url}")
        category_response = fetch(category_url)
    except requests.HTTPError as e:
        print(f"Failed to fetch category: {category_url} -> {e}")
        continue
    sc1 = html.fromstring(category_response.text)
    category_name = ''.join(sc1.xpath("//h1/text()"))
    all_products_link = sc1.xpath('//div[@class="flavor-card"]//a/@href')

    for all_product_link in all_products_link:
        product_url = 'https://www.benjerry.co.uk' + all_product_link
        try:
            print(f"  Fetching product: {product_url}")
            product_response = fetch(product_url)
        except requests.HTTPError as e:
            print(f"  Failed to fetch product: {product_url} -> {e}")
            continue
        sc2 = html.fromstring(product_response.text)

        try:
            product_name = ''.join(sc2.xpath("//h1/text()"))
        except Exception:
            product_name = ''
        try:
            product_description = ''.join(sc2.xpath("//section[@class='flavor-about']/div//text()"))
        except Exception:
            product_description = ''
        try:
            ingredients = ''.join(sc2.xpath("//button[contains(text(),'Ingredients')]/parent::h3/following-sibling::div//p//text()")).replace('Ingredients:','').replace('\n','').strip()
        except Exception:
            ingredients = ''
        try:
            ingredient_image = 'https://www.benjerry.co.uk/' + ''.join(sc2.xpath("//button[contains(text(),'Ingredients')]/parent::h3/following-sibling::div//img/@src"))
        except Exception:
            ingredient_image = ''

        data = {
            'collection_date': date.today().strftime("%b-%d-%Y"),
            'rest_name': "Ben & Jerry's",
            'category_name': category_name,
            'product_name': product_name,
            'product_description': product_description,
            'ingredients': ingredients,
            'ingredient_image': ingredient_image,
        }
        data_store.append(data)

# Write once at the end (GBK blueprint style)
df = pd.DataFrame(data_store)
out_file = os.path.join(path_benjerry, '39_BenJerry_items.csv')
if os.path.exists(out_file):
    df.to_csv(out_file, header=False, index=False, mode='a')
    print("File appended")
else:
    df.to_csv(out_file, header=True, index=False, mode='a')
    print("File created")

print(f"Scraped {len(data_store)} items. Data saved to {out_file}.")



