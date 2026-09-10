import json

import requests

from define_collection_wave import folder
from helpers import create_folder, PDFDownloader

fg_path = create_folder('57_GreeneKing', folder)

# url found at https://www.greeneking.co.uk/pubs/greater-london/silver-cross/menu
urls_fordownload = [
    'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/f414e3b9a77842e48de9c7aa19f0d68c?v=7377cce6',
    'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/681e855a3610418db6b3b6409d5d78e2?v=70e2e7f7',
    'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/1150617f977541aab011459ed035a20b?v=d43c9bf0',
    'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/2ecff6ccd8594977a8dbc89e8ee74f1f?v=f35217d8',
    'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/6ebdcf11763c441f8bc98e39971b5d66?v=770e0c2b'
]

for url in urls_fordownload:
    print("Downloading:", url)
    filePath = fg_path + '/' + url.split('/')[-1].replace('?','_')+'.pdf'
    PDFDownloader(url, filePath=filePath)