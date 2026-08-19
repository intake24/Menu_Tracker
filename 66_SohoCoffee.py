"""Download Soho Coffee's current allergen and nutrition matrices."""

from helpers import combo_PDFDownload


if __name__ == "__main__":
    page = "https://sohocoffee.com/allergens/"
    combo_PDFDownload("66_SohoCoffee", page, keyword="Allergen-Matrix")
    combo_PDFDownload("66_SohoCoffee", page, keyword="Nutritional-Matrix")
