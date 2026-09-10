from helpers import selenium_PDF

if __name__ == "__main__":
    selenium_PDF(
        rest_name="20_ChefBrewer",
        url="https://www.chefandbrewer.com/pubs/cambridgeshire/bridge/menu",
        click_xpath="//*[@class='download-links-legacy-btn var-dark']//button",
        xpath_="//*[@class='download-links-legacy-modal__link']//a",
        wait_time=2,
    )
