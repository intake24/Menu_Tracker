from helpers import selenium_PDF

if __name__ == "__main__":
    selenium_PDF(
        rest_name="6_Dominos",
        url="https://corporate.dominos.co.uk/about-us/our-food/allergens-and-nutrition",
        url_pattern=r"https://dominos\.a\.bigcontent\.io/v1/static/[A-Za-z0-9_./-]+",
        wait_time=2,
    )
