"""Download Pho's current allergen and nutrition guides."""

from helpers import combo_PDFDownload


if __name__ == "__main__":
    page = "https://www.phocafe.co.uk/nutrition/"
    combo_PDFDownload("62_Pho", page, keyword="Guide", prex="https://www.phocafe.co.uk")
