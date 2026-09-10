"""Download Boswell's current nutrition and allergen guides."""

from helpers import combo_PDFDownload


if __name__ == "__main__":
    page = "https://boswellsgroup.com/menu/"
    combo_PDFDownload("44_Boswell", page, keyword="Nutritional")
    combo_PDFDownload("44_Boswell", page, keyword="ALLERGENS")
