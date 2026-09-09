"""Download Krispy Kreme's current nutrition and allergen guide."""

from helpers import selenium_PDF


if __name__ == "__main__":
    selenium_PDF(
        "35_KrispyKreme",
        url="https://app.krispykreme.co.uk/nutritionals",
        xpath_="//a[contains(translate(@href,'PDF','pdf'),'.pdf')]",
        download_via_browser=True,
    )
