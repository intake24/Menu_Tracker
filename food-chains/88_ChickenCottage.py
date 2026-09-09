"""Download Chicken Cottage's current allergen chart.

Chicken Cottage publishes allergens as a single chart image rather than a
PDF or HTML table. The image is downloaded as-is, and OCR'd into a JSON
sidecar file when the optional system `tesseract` binary is available
(same graceful-degradation pattern as 39_BenJerry_selenium.py).
"""

import json
import shutil
import subprocess

import requests
from bs4 import BeautifulSoup

from define_collection_wave import folder
from helpers import create_folder, headers


LANDING_URL = "https://chickencottage.com/allergens/"


def discover_chart_url(html):
    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img", src=True):
        if "allergen" in img["src"].lower():
            return img["src"]
    raise RuntimeError("Chicken Cottage allergen chart image was not found")


def ocr_image(image_bytes):
    if not shutil.which("tesseract"):
        return ""
    result = subprocess.run(
        ["tesseract", "stdin", "stdout", "--psm", "11"],
        input=image_bytes,
        capture_output=True,
        timeout=30,
    )
    return result.stdout.decode(errors="replace").strip() if result.returncode == 0 else ""


if __name__ == "__main__":
    response = requests.get(LANDING_URL, headers=headers, timeout=30)
    response.raise_for_status()
    chart_url = discover_chart_url(response.text)

    image_response = requests.get(chart_url, headers=headers, timeout=30)
    image_response.raise_for_status()

    output_dir = create_folder("88_ChickenCottage", folder)
    filename = chart_url.split("/")[-1].split("?")[0]
    with open(f"{output_dir}/{filename}", "wb") as f:
        f.write(image_response.content)

    ocr_text = ocr_image(image_response.content)
    with open(f"{output_dir}/allergen_chart_ocr.json", "w", encoding="utf-8") as f:
        json.dump({"source_image": chart_url, "ocr_text": ocr_text}, f, indent=2)
