"""Download Greene King's current allergen guides from a representative pub page."""

from helpers import combo_PDFDownload


if __name__ == "__main__":
    combo_PDFDownload(
        "57_GreeneKing",
        "https://www.greeneking.co.uk/pubs/greater-london/silver-cross/allergens",
        keyword="sitecorecontenthub",
    )
