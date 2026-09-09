"""Download Papa Johns' current allergen and nutrition guide."""

from helpers import selenium_PDF


if __name__ == "__main__":
    selenium_PDF(
        "26_PapaJohns",
        url="https://www.papajohns.co.uk/allergens-and-nutrition",
        xpath_="//a[contains(translate(@href,'NUTRITION','nutrition'),'nutrition') and contains(translate(@href,'PDF','pdf'),'.pdf')]",
        download_via_browser=True,
    )
