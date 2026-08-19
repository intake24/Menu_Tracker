"""Download Revolution's current allergen guide from its official media API."""

from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests

from define_collection_wave import folder
from helpers import PDFDownloader, create_folder


MEDIA_API = "https://www.revolution-bars.co.uk/wp-json/wp/v2/media"


def current_allergen_url():
    response = requests.get(
        MEDIA_API,
        params={"search": "allergen", "per_page": 100, "orderby": "date", "order": "desc"},
        timeout=30,
    )
    response.raise_for_status()
    urls = [
        item.get("source_url", "")
        for item in response.json()
        if item.get("date", "").startswith(str(date.today().year))
    ]
    try:
        return next(url for url in urls if url.lower().endswith(".pdf"))
    except StopIteration as error:
        raise RuntimeError(
            "Revolution publishes no current allergen PDF; its authoritative allergen service is unreachable"
        ) from error


if __name__ == "__main__":
    url = current_allergen_url()
    output = Path(create_folder("23_Revolution", folder)) / Path(urlparse(url).path).name
    PDFDownloader(url, str(output))
