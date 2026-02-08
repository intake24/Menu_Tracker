import json
import os
import re
import subprocess
import logging
from ssl import OP_SINGLE_DH_USE
# from tkinter import E
import urllib
from datetime import date
from time import sleep

import pandas as pd
import requests

import undetected_chromedriver as uc

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from fake_useragent import UserAgent
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


import define_collection_wave as dcw
import platform

logger = logging.getLogger(__name__)

def get_chrome_version():
    """Detect the major version of Google Chrome installed on the system."""
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            cmd = r"/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version"
            output = subprocess.check_output(cmd, shell=True).decode()
            version_match = re.search(r"Google Chrome (\d+)", output)
            if version_match:
                return int(version_match.group(1))
        elif system == "Linux":
            cmd = "google-chrome --version"
            output = subprocess.check_output(cmd, shell=True).decode()
            version_match = re.search(r"Google Chrome (\d+)", output)
            if version_match:
                return int(version_match.group(1))
    except Exception as e:
        logger.warning(f"Could not detect Chrome version: {e}")
    return None

def setup_driver(download_dir: str | None = None):
    """Setup Chrome driver with anti-detection options.
    Optionally configures automatic file downloads to download_dir and forces PDFs to download.
    """
    ua = UserAgent()
    random_user_agent = ua.random
    
    # options = Options()
    # options.add_argument('--headless=new')
    # options.add_argument('--no-sandbox')
    # options.add_argument('--disable-dev-shm-usage')
    # options.add_argument(f"--user-agent={random_user_agent}")
    # options.add_argument("--disable-blink-features=AutomationControlled")
    # options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # options.add_experimental_option('useAutomationExtension', False)
    # # Configure downloads if requested
    # if download_dir:
    #     prefs = {
    #         "download.default_directory": download_dir,
    #         "download.prompt_for_download": False,
    #         "download.directory_upgrade": True,
    #         # Force Chrome to download PDFs instead of opening in viewer
    #         "plugins.always_open_pdf_externally": True,
    #     }
    #     options.add_experimental_option("prefs", prefs)
    
    # service = Service(ChromeDriverManager().install())
    # driver = webdriver.Chrome(service=service, options=options)
    
    options = uc.ChromeOptions()
    options.headless = True 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f"--user-agent={random_user_agent}")
    options.add_argument("--disable-blink-features=AutomationControlled")

    chrome_version = get_chrome_version()
    if chrome_version:
        logger.info(f"Detected Chrome version {chrome_version}. Forcing ChromeDriver version match.")
        driver = uc.Chrome(options=options, version_main=chrome_version)
    else:
        driver = uc.Chrome(options=options)
    
    # Remove webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    # In headless mode allow downloads to the specified directory (if provided)
    if download_dir:
        try:
            driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": download_dir
            })
        except Exception:
            pass
    
    return driver

def clean_text(text):
    """Clean text by removing unicode characters and normalizing whitespace"""
    if not text:
        return ""
    # Convert unicode pound sign to proper £ symbol
    cleaned = re.sub(r'\u00a3', '£', text)
    # Remove other problematic unicode characters
    cleaned = re.sub(r'[\u00a0\u2009\u200a\u200b\u2060\ufeff]', ' ', cleaned)
    # Replace multiple whitespace with single space and strip
    cleaned = ' '.join(cleaned.split())
    return cleaned

def setup_driver_colab():
    """Setup Chrome driver with Google Colab specific options"""
    try:
        import google_colab_selenium as gs
    except ImportError:
        raise ImportError("google_colab_selenium is required for Colab environment. Install with: !pip install google_colab_selenium")
    
    # Initialize fake user agent
    ua = UserAgent()
    random_user_agent = ua.random

    options = Options()
    # Add extra options for Colab environment
    options.add_argument("--window-size=1920,1080")  # Set the window size
    options.add_argument("--disable-infobars")  # Disable the infobars
    options.add_argument("--disable-popup-blocking")  # Disable pop-ups
    options.add_argument("--ignore-certificate-errors")  # Ignore certificate errors
    options.add_argument("--incognito")  # Use Chrome in incognito mode
    options.add_argument(f"--user-agent={random_user_agent}")

    driver = gs.UndetectedChrome(options=options)

    # Execute script to remove webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def download_pdf(url, filename, folder_path):
    """Download a PDF file from URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, stream=True)
        response.raise_for_status()
        
        # Ensure filename ends with .pdf
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        
        # Clean filename of invalid characters
        filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        
        file_path = os.path.join(folder_path, filename)
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        
        print(f"Downloaded: {filename}")
        return True
    
    except Exception as e:
        print(f"Error downloading {filename}: {str(e)}")
        return False



# Initialise Selenium web driver
# ua = UserAgent()
# random_user_agent = ua.random

# options = Options()
# options.add_argument('--headless=new')  # Use new headless mode
# options.add_argument('--no-sandbox')
# options.add_argument('--disable-dev-shm-usage')
# options.add_argument(f"--user-agent={random_user_agent}")
# options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_experimental_option("excludeSwitches", ["enable-automation"])
# options.add_experimental_option('useAutomationExtension', False)

# driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# # Execute script to remove webdriver property
# driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

# print(f'header: {random_user_agent}')


# Define paths 
root_path = os.getcwd()
print(f"Root path set to: {root_path}")
# web_browser_path = 'C:\\Users\\angus\\source\\repos\\MenuTracker\\chromedriver.exe'

 # Initialize fake user agent
ua = UserAgent()
random_user_agent = ua.random
headers = {'User-Agent': random_user_agent}


# windows or osx
if platform.system() == 'Windows':
    # headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36'}
    operation_system = 'Windows'
else:
    # headers = {'User-Agent': 'Mozilla/5.0 (Linuxintosh; Intel Linux OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15'}
    operation_system = 'Linux'


# function to remove html tags
def cleanhtml(raw_html):
    '''
    This function removes html tags from raw html texts
    :param raw_html:
    :return: cleaned text file
    '''
    if not raw_html:
        return raw_html
    else:
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext

# function to create a folder for each restaurant
def create_folder(rest_name, folder):
    '''
    Creates a folder for each restaurant under the active collection folder.
    Use `define_collection_wave.folder`.
    '''
    rest_folder  =  rest_name + '_' + date.today().strftime("%b-%d-%Y")
    # Resolve base directory robustly
    base = getattr(dcw, 'folder', None)
    if not os.path.isabs(base):
        base = os.path.join(os.getcwd(), base)
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, rest_folder)
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return path

# function: download a PDF file
def PDFDownloader(url, filePath, verif=True):
    '''
    This function takes in the URL to download a PDF and downloads the PDF file
    :param url: the URL for the PDF
    :param filePath: file path to store the PDF
    :param verif: True or False. Default is set to True. If the PDF download is unsuccessful because of the verification error, set the verif to False
    :return: saves the PDF file
    '''
    ua = UserAgent()
    random_user_agent = ua.random
    headers = {'User-Agent': random_user_agent}
    logger.info(f'headers: {headers}')
    
    r = requests.get(url, stream=True, verify=verif, headers=headers)
    if r.status_code != 200:
        print(f'PDFDownloader: Error {r.status_code} for {url}')
        return
    print(f'PDFDownloader: Downloading PDF for {url}')
    print(f'PDFDownloader: file size {r.headers.get("Content-Length", "unknown")} bytes')
    with open(filePath, "wb") as pdf:
        for chunk in r.iter_content(chunk_size=1024):
            # writing one chunk at a time to a pdf file
            if chunk:
                pdf.write(chunk)

# Downloading multiple PDFs
def combo_PDFDownload(rest_name, url, keyword='pdf', prex=None, verify=True, timeout: int = 30):
    '''
    This function identifies all PDFs available for download and save all of them
    :param rest_name: the name of the restaurant
    :param url: URL for downloading the PDFs
    :param keyword: keyword for identifying the PDF download link. The default is set to 'pdf'
    :param prex: if the PDF download link does not contain domain link, add the domain url here
    :param verify: True or False. whether to allow authentication
    :return: multiple downloaded PDFs
    '''
    logger.info("Starting combo_PDFDownload")
    ua = UserAgent()
    random_user_agent = ua.random
    headers = {'User-Agent': random_user_agent}
    logger.info(f'headers: {headers}')
    
    # Use live collection folder from define_collection_wave when available
    base_folder = getattr(dcw, 'folder', None)
    path = create_folder(rest_name, base_folder)
    try:
        html = requests.get(url, headers=headers, verify=verify, timeout=timeout)
    except requests.RequestException as e:
        logger.error(f"Request error for {url}: {e}")
        return
    logger.info(f'HTTP status {html.status_code} for {url}')
    if html.status_code != 200:
        logger.warning(f'Non-200 status {html.status_code} for {url}; aborting')
        return
    soup = BeautifulSoup(html.text, 'html.parser')
    # Support both anchor hrefs and button data-url attributes containing the keyword.
    elements = soup.select(f"a[href*='{keyword}'], button[data-url*='{keyword}']")
    if not elements:
        logger.info(f'No PDF candidate elements found for {rest_name} at {url}')
        return

    seen = set()
    for el in elements:
        href = el.get('href') or el.get('data-url')
        if not href:
            continue
        url_link = href.strip()
        # Normalise relative URLs (prefix only applied when provided)
        if 'https://' not in url_link and 'http://' not in url_link and prex:
            if not url_link.startswith('/'):
                url_link = '/' + url_link
            url_link = prex + url_link
        # Deduplicate
        if url_link in seen:
            continue
        seen.add(url_link)

        filename = url_link.split('/')[-1]
        if not filename.lower().endswith('pdf'):
            if '.pdf' in filename.lower():
                filename = filename.split('?')[0]
            else:
                filename = filename + '.pdf'
        filename = filename.replace(':', '').replace('?', '')
        filePath = os.path.join(path, filename)
        logger.info(f'Downloading: {url_link} -> {filePath}')
        PDFDownloader(url=url_link, filePath=filePath)
    logger.info('Finished downloading PDFs for ' + rest_name)

def combo_PDFDownload_class_name(rest_name, url, keyword='pdf', prex=None, verify=True):
    '''
    This function identifies all PDFs available for download and save all of them
    It finds the links by keywords in the class name instead of href
    :param rest_name: the name of the restaurant
    :param url: URL for downloading the PDFs
    :param keyword: keyword for identifying the PDF download link. The default is set to 'pdf'
    :param prex: if the PDF download link does not contain domain link, add the domain url here
    :param verify: True or False. whether to allow authentication
    :return: multiple downloaded PDFs
    '''
    # Use live collection folder from define_collection_wave when available
    base_folder = getattr(dcw, 'folder', None)
    path = create_folder(rest_name, base_folder)
    html = requests.get(url, headers=headers, verify=verify)
    soup = BeautifulSoup(html.text, 'html.parser')
    urls = soup.select(f"a[class*={keyword}]")
    filenames = soup.select(f"span[class*={keyword}]")
    for i in range(len(urls)):
        url = urls[i]
        url_link = url.get('href') 
        filename = filenames[i].text + '.pdf'
        filePath = os.path.join(path,  filename)
        print(url_link)
        print(filePath)
        PDFDownloader(url=url_link, filePath=filePath)
    print('finished downloading pdfs for ' + rest_name)

# Download PDFs with Selenium - unified function replacing vue_PDF and java_PDF
def selenium_PDF(rest_name, url, xpath_=None, prefix=None, use_partial_link_text=False, 
                 partial_link_value='Download', navigate_to_links=False, wait_time=5,
                 handle_runtime_pdf: bool = True, download_filename: str | None = None):
    """
    Download PDFs using Selenium with flexible link discovery options.
    
    Args:
        rest_name: Restaurant name for folder creation
        url: Source URL to scrape
        xpath_: XPath selector for finding PDF links (when use_partial_link_text=False)
        prefix: URL prefix to prepend to relative links
        use_partial_link_text: If True, use PARTIAL_LINK_TEXT instead of XPath
        partial_link_value: Text to search for when use_partial_link_text=True
        navigate_to_links: If True, navigate to each link to get final URL
        wait_time: Seconds to wait between operations
    """
    # Create folder and configure driver to download into it when handling runtime PDFs
    path = create_folder(rest_name, getattr(dcw, 'folder', None))
    driver = setup_driver(download_dir=path if handle_runtime_pdf else None)
    
    try:
        print(f'1. Source URL: {url}')
        
        print(f'2. Browsing: {url}')
        driver.get(url)
        sleep(wait_time)
        
        # Helper: wait for a new PDF file to appear in download dir
        def wait_for_new_pdf(dir_path: str, before_set: set[str], timeout: int = 60) -> str | None:
            import time as _t
            end = _t.time() + timeout
            while _t.time() < end:
                files = {f for f in os.listdir(dir_path) if f.lower().endswith(('.pdf', '.crdownload'))}
                # Ignore temp download files still in progress
                finished = {f for f in files if not f.endswith('.crdownload')}
                new_files = finished - before_set
                if new_files:
                    return os.path.join(dir_path, sorted(new_files)[-1])
                _t.sleep(0.5)
            return None

        # Discover potential links or buttons
        elements = []
        if use_partial_link_text and partial_link_value:
            print(f'3. Finding elements by partial text: {partial_link_value}')
            elements = driver.find_elements(By.PARTIAL_LINK_TEXT, partial_link_value)
        elif xpath_:
            print(f'3. Finding elements by XPath: {xpath_}')
            elements = driver.find_elements(By.XPATH, xpath_)
        else:
            # Generic fallbacks commonly seen on Ten Kites
            print('3. Finding default PDF triggers (Download|PDF|Allergen)')
            elements = driver.find_elements(By.XPATH, "//a[contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'pdf') or contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'download') or contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'allergen')] | //button[contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'pdf') or contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'download') or contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'allergen')] ")

        print(f'4. Found {len(elements)} potential PDF trigger(s)')

        # First try href-based downloads via requests
        links = []
        for el in elements:
            href = el.get_attribute('href')
            if href:
                links.append(href)

        if links:
            for i, link in enumerate(links):
                if navigate_to_links:
                    print(f'5.{i+1} Navigating to: {link}')
                    driver.get(link)
                    link = driver.current_url
                    sleep(wait_time)

                # Handle relative URLs
                if prefix and 'https://' not in link and 'http://' not in link:
                    if not link.startswith('/'):
                        link = '/' + link
                    link = prefix + link

                # Determine filename
                filename = download_filename or link.split('/')[-1]
                if not filename.lower().endswith('.pdf'):
                    if '.pdf' in filename.lower():
                        filename = filename.split('?')[0]
                    else:
                        filename = filename + '.pdf'
                filename = filename.replace(':', '').replace('?', '')

                file_path = os.path.join(path, filename)
                print(f'6.{i+1} Downloading via HTTP: {link} -> {file_path}')
                PDFDownloader(url=link, filePath=file_path)
        elif handle_runtime_pdf:
            # Click-based runtime PDF generation, rely on Chrome download behavior
            print('5. No direct links found; attempting click-to-download for runtime-generated PDF')
            before = {f for f in os.listdir(path) if f.lower().endswith('.pdf')}
            clicked = False
            for el in elements:
                try:
                    driver.execute_script("arguments[0].click();", el)
                    clicked = True
                    break
                except Exception:
                    continue
            if not clicked:
                # As a fallback try common buttons
                try:
                    btns = driver.find_elements(By.XPATH, "//button|//a")
                    for b in btns:
                        txt = (b.text or '').lower()
                        if any(k in txt for k in ['pdf', 'download', 'allergen']):
                            driver.execute_script("arguments[0].click();", b)
                            clicked = True
                            break
                except Exception:
                    pass

            if clicked:
                downloaded = wait_for_new_pdf(path, before_set=before, timeout=90)
                if downloaded and download_filename:
                    # Rename to desired filename
                    final_path = os.path.join(path, download_filename if download_filename.lower().endswith('.pdf') else download_filename + '.pdf')
                    try:
                        os.replace(downloaded, final_path)
                        print(f'6. Saved runtime PDF to: {final_path}')
                    except Exception:
                        print(f'6. Saved runtime PDF to: {downloaded}')
                elif downloaded:
                    print(f'6. Saved runtime PDF to: {downloaded}')
                else:
                    print('6. Timed out waiting for runtime-generated PDF download')
            else:
                print('5. Could not click any candidate element to trigger PDF')
        
        print(f'7. Finished downloading PDFs for {rest_name}')
        
    finally:
        driver.quit()


# Legacy functions for backward compatibility
def vue_PDF(rest_name, url, xpath_=None):
    """Legacy function - use selenium_PDF instead"""
    return selenium_PDF(rest_name, url, xpath_=xpath_, wait_time=10)


def java_PDF(rest_name, url, prex=None, link_=True, xpath_=None, value='media'):
    """Legacy function - use selenium_PDF instead"""
    return selenium_PDF(
        rest_name=rest_name,
        url=url,
        prefix=prex,
        use_partial_link_text=link_,
        partial_link_value=value if value else 'Download',
        xpath_=xpath_,
        navigate_to_links=True,
        wait_time=5
    )

def IMGDownloader(url, filePath):
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36')]
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(url, filePath)


def combo_imgDownload(rest_name,url,folder):
    path = create_folder(rest_name, folder)
    # s = Service(web_browser_path)
    # browser = webdriver.Chrome(service=s)
    # browser.get(url)
    driver = setup_driver()
    driver.get(url)

    sleep(10)
    images = driver.find_elements(by=By.XPATH, value='//img[contains(@src, "jpg")]')
    for image in images:
        image_link = image.get_attribute("src")
        print(image_link)
        image_name = image_link.split('/')[-1]
        image_path = os.path.join(path, image_name)
        IMGDownloader(image_link,image_path)


# function: create a folder and run the spider
def RunSpider(spidername, folder, json_=False):
    '''
    This function allows the spiders to run and saves the spider outputs
    :param spidername: the name of the spider you want to run
    :param folder: folder for the data collection wave
    :param json_: Default is False (file saving as csv).
    :return: spider output saved in csv or json
    '''
    #op_sys = platform.system() # for the windows system, I will use the relative path for the file storage path
    #print(op_sys)
    os.chdir(root_path)
    path = create_folder(spidername, folder) # create a folder for the spider output
    os.chdir('./Scrapy_spiders')
    if json_:
        json_file_name = spidername + '_items.json'
        json_file_path_root = os.path.join(root_path, path, json_file_name)
        os.system("scrapy crawl " + spidername + " -o" + json_file_path_root)
        with open(json_file_path_root,'r') as jsonfile:
            json_data = json.load(jsonfile)
            json_df = pd.DataFrame(json_data)
            json_df.to_csv(json_file_path_root.replace('.json', '.csv'), index=False)
    else:
        csv_file_name = spidername + '_items.csv'
        csv_file_path_root = os.path.join(root_path, path, csv_file_name)
        cmd = "scrapy crawl " + spidername + " -o " + csv_file_path_root
        print('cmd=' + cmd)
        # os.system("scrapy crawl " + spidername + " -o " + csv_file_path_root)
    os.chdir(root_path)
    print('root_path=' + root_path)
    print('finished scraping ' + spidername)

# function: run the script for a restaurant (requests)
def RunScript(rest_name):
    try:
        # Use subprocess instead of os.system to capture output
        result = subprocess.run(['python', rest_name + '.py'], 
                              capture_output=True, 
                              text=True)
        
        print(f"=== STDOUT for {rest_name} ===")
        print(result.stdout)
        
        print(f"=== STDERR for {rest_name} ===")
        print(result.stderr)
        
        print(f"=== Return code: {result.returncode} ===")
        
        if result.returncode == 0:
            print('Successfully scraped ' + rest_name)
        else:
            print(f'Issues with {rest_name}. Please Review')
            
    except Exception as e:
        print(f'Exception running {rest_name}: {e}')

# Downloading PDF for Greene King companies
def greene_king_download(rest_name, id, url, folder):
    path = create_folder(rest_name, folder)
    # graphsql 
    request_url ='https://menufinder.greeneking-pubs.co.uk/graphql'
    query_string = "query Menus($venueId: String!) {\n  menus(venueId: $venueId) {\n    id\n    name\n    slug\n    description\n    image\n  }\n}\n"
    payload = {"operationName":"Menus","variables":{"venueId":id},"query":query_string}
    menus = requests.post(request_url, headers = headers, json = payload).json().get('data').get('menus')
    for menu in menus:
        menu_name = menu.get('name')
        print(menu_name + 'Downloading ---->')
        menu_id = menu.get('id')
        # now another post request to get the download link 
        query_string_menu = {"operationName":"MenuPages","variables":{"venueId":id,"menuId":menu_id},"query":"query MenuPages($venueId: String!, $menuId: Int!) {\n  menuPages(venueId: $venueId, menuId: $menuId) {\n    id\n    name\n    downloads {\n      download\n      allergens\n      nutrition\n    }\n    keywords {\n      id\n      name\n      icon\n    }\n    displayGroups {\n      id\n      name\n      groupHeader\n      groupFooter\n      products {\n        id\n        name\n        description\n        new\n        showPrices\n        keywords\n        portions {\n          id\n          name\n          portionName\n          abbreviation\n          price\n        }\n      }\n    }\n  }\n}\n"}
        menu_urls = requests.post(request_url, headers= headers, json = query_string_menu).json().get('data').get('menuPages').get('downloads')
        for value in menu_urls.values():
            if value is not None:
                url_pdf = url + value
                path_temp = os.path.join(path, url_pdf.split('/')[-1]) # path to save the PDF file
                PDFDownloader(url_pdf, path_temp)

def try_click_accept_cookies(driver) -> None:
    """Attempt to accept cookies banner to unblock interactions."""
    try:
        print("Trying to accept cookies banner if present...")
        # Try several common selectors/texts
        candidates = [
            (By.XPATH, "//button[contains(translate(., 'ACCEPT', 'accept'), 'accept')]") ,
            (By.XPATH, "//a[contains(translate(., 'ACCEPT', 'accept'), 'accept')]") ,
            (By.XPATH, "//button[contains(., 'ACCEPT ALL COOKIES') or contains(., 'Accept All Cookies')]") ,
        ]
        for by, sel in candidates:
            elems = driver.find_elements(by, sel)
            if elems:
                try:
                    elems[0].click()
                    WebDriverWait(driver, 2).until(lambda d: True)
                    print("Cookies banner accepted.")
                    break
                except Exception:
                    print("Failed to accept cookies banner.")
                    continue
    except Exception:
        pass

def get_visible_text(el, driver) -> str:
    """Return best-effort visible text from an element (text, innerText, textContent)."""
    try:
        t = (el.text or "").strip()
        if t:
            return t
    except Exception:
        pass
    try:
        t = driver.execute_script(
            "return (arguments[0].innerText || arguments[0].textContent || '').trim();", el
        )
        if t:
            return t
    except Exception:
        pass
    return ""

def set_driver_timeouts(driver):
    """Configure driver timeouts to reduce flaky transport timeouts while avoiding long stalls."""
    try:
        driver.set_page_load_timeout(20)
        driver.set_script_timeout(5)
    except Exception as e:
        print(f"Could not set timeouts: {e}")
        pass

def safe_get(driver, url: str, wait_locator=None, wait_timeout: int = 6) -> 'WebDriver':
    """
    Navigate robustly to url.
    - On page-load TimeoutException, issue window.stop() and proceed.
    - On transport read timeout or driver hang, restart the driver, re-apply timeouts, accept cookies, and retry once.
    Returns the (possibly restarted) driver.
    """

    def _navigate(drv):
        try:
            drv.get(url)
        except TimeoutException:
            # Stop loading and proceed to wait on required DOM instead of failing
            try:
                drv.execute_script("window.stop();")
            except Exception:
                pass
        # Optionally wait for a page element that signals readiness
        if wait_locator:
            try:
                WebDriverWait(drv, wait_timeout).until(EC.presence_of_element_located(wait_locator))
            except Exception:
                # Best-effort wait; do not fail navigation outright
                print("Wait for locator timed out; proceeding anyway…")
                pass

    # Try to quit existing selenium driver and create a new one
    try:
        driver.quit()
    except Exception as e:
        print("Cannot destroy existing web driver, proceeding anyway...")
    try:
        new_driver = setup_driver()
        set_driver_timeouts(new_driver)
        try_click_accept_cookies(new_driver)
        _navigate(new_driver)
        return new_driver
    except WebDriverException as e:
        msg = str(e)
        if ("Read timed out" in msg) or ("HTTPConnectionPool" in msg) or ("ERR_CONNECTION" in msg):
            # Restart the driver and retry once
            try:
                print("Transport timeout detected, restarting driver and retrying navigation…")
                new_driver.quit()
            except Exception:
                print("Could not quit driver cleanly, proceeding anyway…")
                pass
            new_driver = setup_driver()
            set_driver_timeouts(new_driver)
            try_click_accept_cookies(new_driver)
            _navigate(new_driver)
            logger.info("Re-created driver and retry successful")
            return new_driver
        # Unexpected error; bubble up
        raise
