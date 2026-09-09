"""Download Tortilla's current nutrition and allergen guide.

The site replaced its interactive per-item nutrition calculator with a
single downloadable PDF; download that directly instead of scraping it.
"""

from helpers import combo_PDFDownload


if __name__ == "__main__":
    page = "https://www.tortilla.co.uk/menu/nutrition-and-allergens"
    combo_PDFDownload("79_Tortilla", page, keyword="nutrition-guide")
