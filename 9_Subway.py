from helpers import selenium_PDF


if __name__ == "__main__":
    selenium_PDF(
        rest_name="9_Subway",
        url="https://www.subway.com/en-gb/menunutrition/nutrition",
        xpath_="//a[contains(translate(@href, 'PDF', 'pdf'), '.pdf')]",
        wait_time=5,
        download_via_browser=True,
    )
