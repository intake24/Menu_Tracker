"""Download Wasabi's current nutritional guide."""

from helpers import combo_PDFDownload


if __name__ == "__main__":
    page = "https://www.wasabi.uk.com/menus/"
    combo_PDFDownload("76_Wasabi", page, keyword="Nutritional")
