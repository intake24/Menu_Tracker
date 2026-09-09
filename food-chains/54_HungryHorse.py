import json

import requests

from define_collection_wave import folder
from helpers import create_folder, PDFDownloader

fg_path = create_folder('54_HungryHorse', folder)

url_fordownload = [
'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/e466f55943f3452a93c9ec9d9315e543?v=0b460e3b', 
'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/6e2804b5e78349f586d714bb835a6f32?v=6408983c',
'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/4abef2cb48c947c99a06e73ad9b0b2d2?v=eb780b84'
]
for url in url_fordownload:
    print("Downloading:", url)
    filePath = fg_path + '/' + url.split('/')[-1].replace('-','_').replace('?','')+'.pdf'
    PDFDownloader(url, filePath=filePath)
