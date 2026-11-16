"""Download Five Guys UK's current nutrition and allergen guide.

The PDF filename changes with every product update, so the button's own
link text ("UK Nutrition & Allergen Guide") is used to find it rather than
a keyword in the URL.
"""

import time

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


def fetch_landing(attempts=3):
    """Cloudflare intermittently answers 403 from the server; retry before failing."""
    for attempt in range(1, attempts + 1):
        response = requests.get(LANDING_URL, headers=headers, timeout=30)
        if response.status_code != 403 or attempt == attempts:
            response.raise_for_status()
            return response
        print(f"403 from {LANDING_URL} (attempt {attempt}/{attempts}); retrying in {30 * attempt}s")
        time.sleep(30 * attempt)


if __name__ == "__main__":
    response = fetch_landing()
    pdf_url = discover_guide_url(response.text)

    output_dir = create_folder("52_FiveGuys", folder)
    filename = pdf_url.split("/")[-1].split("?")[0]
    PDFDownloader(pdf_url, filePath=f"{output_dir}/{filename}")
