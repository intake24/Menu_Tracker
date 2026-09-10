import json

import requests

from define_collection_wave import folder
from helpers import create_folder, PDFDownloader


fg_path = create_folder('51_FarmhouseInns', folder)
print(fg_path)

url_fordownload = 'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/1bbe74a89dd140b2a5f2fb881731b286?v=b99b8d6e'
print("Downloading:", url_fordownload)
filePath = fg_path + '/' + url_fordownload.split('/')[-1].replace('-','_').replace('?','')+'.pdf'
PDFDownloader(url_fordownload, filePath=filePath)
