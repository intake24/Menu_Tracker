import os
import csv
import json
from datetime import date
from typing import List, Dict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Project helpers and collection management
import define_collection_wave as dcw
from define_collection_wave import folder as collection_folder
from helpers import create_folder, PDFDownloader

BASE_URL = "https://www.myvue.com/legal/nutritional-information"
REST_NAME = "Vue"
FOLDER_KEY = "58_Vue"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def ensure_collection_folder() -> str:
    """Ensure a valid collection folder exists and return path for this script.
    Initializes a default collection if none is set to make this runnable standalone/Colab.
    """
    global collection_folder
    if not collection_folder:
        # Fall back to a sane default so the script runs standalone
        dcw.create_collection("default_collection")
    # Use project-standard folder convention like other scripts
    path_out = create_folder(FOLDER_KEY, dcw.folder)
    os.makedirs(path_out, exist_ok=True)
    return path_out


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def is_pdf_href(href: str) -> bool:
    if not href:
        return False
    href_l = href.lower()
    # accept .pdf links even with query params
    return ".pdf" in href_l and (href_l.endswith(".pdf") or ".pdf?" in href_l)


def discover_pdf_links(page_url: str) -> List[str]:
    """Parse the Vue legal nutrition page and return absolute PDF URLs.
    Robust to relative links, ignores non-http(s) schemes, and deduplicates.
    """
    html = fetch_html(page_url)
    soup = BeautifulSoup(html, "html.parser")

    pdf_urls: List[str] = []
    seen: set[str] = set()

    # Primary: any anchor with href containing/ending in .pdf
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href:
            continue
        if not is_pdf_href(href):
            continue
        abs_url = urljoin(page_url, href)
        if abs_url.startswith("http://") or abs_url.startswith("https://"):
            if abs_url not in seen:
                seen.add(abs_url)
                pdf_urls.append(abs_url)

    return pdf_urls


def sanitize_filename(name: str) -> str:
    # Keep simple alnum and set of characters, strip trailing spaces
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "-", "_", "."))
    safe = safe.strip()
    if not safe.lower().endswith(".pdf"):
        if ".pdf" in safe.lower():
            safe = safe[: safe.lower().rfind(".pdf") + 4]
        else:
            safe += ".pdf"
    return safe or "file.pdf"


def download_pdfs(pdf_urls: List[str], out_dir: str) -> List[Dict]:
    """Download all given PDF URLs into out_dir and return a manifest list."""
    os.makedirs(out_dir, exist_ok=True)
    manifest: List[Dict] = []
    collection_date = date.today().strftime("%b-%d-%Y")

    for url in pdf_urls:
        filename = sanitize_filename(os.path.basename(url.split("?", 1)[0]))
        target_path = os.path.join(out_dir, filename)
        try:
            PDFDownloader(url=url, filePath=target_path)
            manifest.append(
                {
                    "rest_name": REST_NAME,
                    "collection_date": collection_date,
                    "pdf_url": url,
                    "file_name": filename,
                    "saved_path": target_path,
                }
            )
        except Exception as e:
            # Keep going on download issues
            print(f"Failed to download {url}: {e}")
            continue

    return manifest


def write_manifests(manifest: List[Dict], out_dir: str) -> None:
    # JSON manifest
    json_path = os.path.join(out_dir, "vue_pdfs.json")
    with open(json_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # CSV manifest
    csv_path = os.path.join(out_dir, "vue_pdfs.csv")
    fieldnames = ["rest_name", "collection_date", "pdf_url", "file_name", "saved_path"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in manifest:
            writer.writerow({k: row.get(k) for k in fieldnames})

    print(f"Saved JSON manifest: {json_path}")
    print(f"Saved CSV manifest: {csv_path}")


def main() -> None:
    out_dir = ensure_collection_folder()
    print(f"Output folder: {out_dir}")

    print(f"Discovering PDFs from: {BASE_URL}")
    pdf_urls = discover_pdf_links(BASE_URL)
    if not pdf_urls:
        print("No PDF links found on the page.")
        return

    print(f"Found {len(pdf_urls)} PDF link(s). Starting downloads…")
    manifest = download_pdfs(pdf_urls, out_dir)
    print(f"Downloaded {len(manifest)}/{len(pdf_urls)} files.")

    write_manifests(manifest, out_dir)


if __name__ == "__main__":
    main()
