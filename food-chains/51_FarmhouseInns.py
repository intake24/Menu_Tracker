"""Download Farmhouse Inns' current allergen guide from a representative pub page.

The old hardcoded sitecorecontenthub content ID is tied to one menu season;
discover the current link from a stable pub page instead.
"""

from helpers import combo_PDFDownload


if __name__ == "__main__":
    combo_PDFDownload(
        "51_FarmhouseInns",
        "https://www.farmhouseinns.co.uk/pubs/bedfordshire/maypole-farm/allergens",
        keyword="sitecorecontenthub",
    )
