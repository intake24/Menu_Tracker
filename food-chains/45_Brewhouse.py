"""Download Brewhouse & Kitchen's current allergen matrix."""

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from helpers import combo_PDFDownload


if __name__ == "__main__":
    page = "https://www.brewhouseandkitchen.com/allergens"
    response = requests.get(page, timeout=30)
    response.raise_for_status()
    link = BeautifulSoup(response.text, "html.parser").select_one("a[href*='brewhouse-allergens']")
    if not link:
        raise RuntimeError("Brewhouse & Kitchen published no allergen menu link")
    combo_PDFDownload("45_Brewhouse", urljoin(page, link["href"]))
