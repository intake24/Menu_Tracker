"""Download Krispy Kreme's current nutrition and allergen guide."""

from helpers import selenium_PDF


if __name__ == "__main__":
    selenium_PDF(
        "35_KrispyKreme",
        url="https://app.krispykreme.co.uk/nutritionals",
        xpath_="//a[contains(translate(@href,'PDF','pdf'),'.pdf')]",
        wait_time=10,  # app.krispykreme.co.uk is JS-rendered; render time varies
        wait_for_xpath=True,
        retries=3,  # 10s, 20s, 40s
    )
