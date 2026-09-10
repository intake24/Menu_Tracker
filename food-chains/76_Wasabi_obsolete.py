import json

import requests

from define_collection_wave import folder
from helpers import create_folder, PDFDownloader


fg_path = create_folder('76_Wasabi', folder)
print(fg_path)

url_fordownload = 'https://www.wasabi.uk.com/wp-content/uploads/2024/11/WAS_Nutritional_Guide_141124v1.pdf'
print("Downloading:", url_fordownload)
filePath = fg_path + '/' + url_fordownload.split('/')[-1].replace('-','_').replace('?','')+'.pdf'
PDFDownloader(url_fordownload, filePath=filePath)
