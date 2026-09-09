"""Download Five Guys UK's current nutrition and allergen guide.

The PDF filename changes with every product update, so the button's own
link text ("UK Nutrition & Allergen Guide") is used to find it rather than
a keyword in the URL.
"""

import requests
from bs4 import BeautifulSoup

from define_collection_wave import folder
from helpers import create_folder, PDFDownloader, headers


LANDING_URL = "https://www.fiveguys.co.uk/nutritional-allergy-information/"
LINK_TEXT = "uk nutrition & allergen guide"


def discover_guide_url(html):
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        if LINK_TEXT in link.get_text(" ", strip=True).lower():
            return link["href"]
    raise RuntimeError("Five Guys UK nutrition & allergen guide link was not found")


if __name__ == "__main__":
    response = requests.get(LANDING_URL, headers=headers, timeout=30)
    response.raise_for_status()
    pdf_url = discover_guide_url(response.text)

    output_dir = create_folder("52_FiveGuys", folder)
    filename = pdf_url.split("/")[-1].split("?")[0]
    PDFDownloader(pdf_url, filePath=f"{output_dir}/{filename}")
