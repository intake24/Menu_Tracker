"""Download Cineworld's current allergen and nutrition guide."""

from helpers import combo_PDFDownload


if __name__ == "__main__":
    combo_PDFDownload(
        "46_Cineworld",
        "https://www.cineworld.co.uk/static/en/uk/allergens-and-nutrition",
        prex="https://www.cineworld.co.uk",
    )
