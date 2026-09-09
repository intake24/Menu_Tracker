"""Download ODEON's current UK food/drink nutrition and allergen PDFs.

Plain requests hit ODEON's queue-it waiting-room wall; a real browser
session gets past it, so this uses Selenium purely to fetch the page.
"""

import re
from urllib.parse import urljoin

from define_collection_wave import folder
from helpers import create_folder, setup_driver, PDFDownloader


LANDING_URL = "https://www.odeon.co.uk/experiences/food-drinks/food-and-drinks-facts-and-figures/"


def discover_uk_pdf_urls(html, base_url):
    urls = re.findall(r'href="([^"]*\.pdf[^"]*)"', html)
    return [
        urljoin(base_url, url)
        for url in urls
        if "uk-version" in url.lower()
    ]


if __name__ == "__main__":
    driver = setup_driver()
    try:
        driver.get(LANDING_URL)
        pdf_urls = discover_uk_pdf_urls(driver.page_source, LANDING_URL)
    finally:
        driver.quit()

    if not pdf_urls:
        raise RuntimeError("No ODEON UK nutrition/allergen PDFs were found")

    output_dir = create_folder("59_Odeon", folder)
    for url in pdf_urls:
        filename = url.split("/")[-1].split("?")[0]
        PDFDownloader(url, filePath=f"{output_dir}/{filename}")
