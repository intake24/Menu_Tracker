import json

import requests

from define_collection_wave import folder
from helpers import create_folder, PDFDownloader


fg_path = create_folder('31_FlamingGrill', folder)
print(fg_path)

urls_fordownload = ['https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/7fc3191a29194b6e87d731c6980a0ad9?v=ad3101c6',
                    'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/04578ae0131a47f4bca421ba9a8094c6?v=e6408b52',
                    'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/23b8547a88b64c909bb5d116246cedbf?v=b03de5f4',
                    'https://gkbr-p-001.sitecorecontenthub.cloud/api/public/content/521c6742f2ba49c6999a570467d1bbc2?v=ae424d24']
for url in urls_fordownload:
    print("Downloading:", url)
    filePath = fg_path + '/' + url.split('/')[-1].replace('-','_').replace('?','')+'.pdf'
    PDFDownloader(url, filePath=filePath)
