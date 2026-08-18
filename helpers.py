import json
import os
import re
import shutil
import subprocess
import logging
from ssl import OP_SINGLE_DH_USE
# from tkinter import E
import urllib
from datetime import date
from pathlib import Path
from time import sleep

import pandas as pd
import requests

import undetected_chromedriver as uc

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from fake_useragent import UserAgent
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


import define_collection_wave as dcw
import platform

logger = logging.getLogger(__name__)


def find_cached_chromedriver(chrome_version: int, search_roots=None):
    """Return a local ChromeDriver matching the installed Chrome major version."""
    roots = search_roots or [
        Path(__file__).resolve().parent / ".drivers",
        Path.home() / ".wdm" / "drivers" / "chromedriver",
    ]
    version_prefix = f"{chrome_version}."
    candidates = []

    for root in map(Path, roots):
        if not root.exists():
            continue
        for path in root.rglob("chromedriver"):
            if path.is_file() and any(
                part.startswith(version_prefix) for part in path.parts
            ):
                candidates.append(path)

    if not candidates:
        return None
    return str(max(candidates, key=lambda path: path.stat().st_mtime))


def prepare_cached_chromedriver(driver_path: str, chrome_version: int):
    """Patch a cached driver and repair its macOS signature before launch."""
    patcher = uc.Patcher(
        executable_path=driver_path,
        version_main=chrome_version,
    )
    if not patcher.is_binary_patched(driver_path):
        patcher.patch_exe()

    if platform.system() == "Darwin":
        subprocess.run(
            ["codesign", "--force", "--sign", "-", driver_path],
            check=True,
            capture_output=True,
        )
    return driver_path


def get_chrome_binary_and_version():
    """Return the installed Chrome/Chromium binary and its major version."""
    candidates = (
        [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        if platform.system() == "Darwin"
        else ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]
    )
    for candidate in candidates:
        binary = candidate if Path(candidate).is_file() else shutil.which(candidate)
        if not binary:
            continue
        try:
            output = subprocess.check_output(
                [binary, "--version"], text=True, stderr=subprocess.STDOUT
            )
        except (OSError, subprocess.CalledProcessError):
            continue
        version = re.search(r"\b(\d+)(?:\.\d+)+", output)
        if version:
            return binary, int(version.group(1))
    logger.warning("Could not detect a Chrome or Chromium installation")
    return None, None


def get_chrome_version():
    """Return the installed Chrome/Chromium major version."""
    return get_chrome_binary_and_version()[1]

def setup_driver(download_dir: str | None = None, extra_chrome_args: list[str] | None = None):
    """Setup Chrome driver with anti-detection options.

    Tries undetected_chromedriver first (better bot-detection evasion).
    Falls back to plain webdriver.Chrome via Selenium Manager when the
    uc driver download or launch fails (e.g. flaky network).

    The fallback always includes ``--disable-http2`` to avoid
    ERR_HTTP2_PROTOCOL_ERROR on sites that reject HTTP/2 from headless
    Chrome (harmless on sites that accept it).

    Args:
        download_dir: Optional directory for automatic file downloads.
        extra_chrome_args: Optional list of additional Chrome CLI flags
            applied to *both* the uc and fallback driver.
    """
    ua = UserAgent()
    random_user_agent = ua.random
    extra = extra_chrome_args or []
    chrome_binary, chrome_version = get_chrome_binary_and_version()
    cached_driver = (
        find_cached_chromedriver(chrome_version) if chrome_version else None
    )
    if cached_driver:
        cached_driver = prepare_cached_chromedriver(
            cached_driver,
            chrome_version,
        )

    # --- Try undetected_chromedriver first ---
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            options = uc.ChromeOptions()
            if chrome_binary:
                options.binary_location = chrome_binary
            options.headless = True
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f"--user-agent={random_user_agent}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            if download_dir:
                options.add_experimental_option("prefs", {
                    "download.default_directory": download_dir,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "plugins.always_open_pdf_externally": True,
                })
            for arg in extra:
                options.add_argument(arg)

            if chrome_version:
                logger.info(f"Detected Chrome version {chrome_version}. Forcing ChromeDriver version match.")
                if cached_driver:
                    logger.info("Using cached ChromeDriver: %s", cached_driver)
                driver = uc.Chrome(
                    options=options,
                    version_main=chrome_version,
                    driver_executable_path=cached_driver,
                )
            else:
                driver = uc.Chrome(options=options)

            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            if download_dir:
                try:
                    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                        "behavior": "allow",
                        "downloadPath": download_dir
                    })
                except Exception:
                    pass

            return driver

        except Exception as exc:
            logger.warning(f"setup_driver() attempt {attempt}/{max_attempts} failed: {exc}")
            if attempt < max_attempts:
                sleep(1)

    # --- Fallback: plain webdriver.Chrome via Selenium Manager ---
    logger.warning("Primary setup_driver() failed, falling back to webdriver.Chrome()")
    fallback_args = ['--disable-http2'] + extra
    opts = Options()
    if chrome_binary:
        opts.binary_location = chrome_binary
    opts.add_argument('--headless=new')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.add_argument(f"--user-agent={random_user_agent}")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    for arg in fallback_args:
        opts.add_argument(arg)
    if download_dir:
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        }
        opts.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=opts)
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
    if base is None:
        raise RuntimeError("Collection folder not set. Call define_collection_wave.create_collection() first.")
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
    urls = [el.get('href') or el.get('data-url') for el in elements]
    if not urls:
        # Some PDF viewers keep their URL only in an inline script.
        urls = [
            candidate
            for candidate in re.findall(r"https?://[^\s\"'<>]+?\.pdf(?:\?[^\s\"'<>]*)?", html.text, flags=re.IGNORECASE)
            if re.match(r"https?://[^?#]+\.pdf(?:[?#]|$)", candidate, flags=re.IGNORECASE)
        ]
    if not urls:
        logger.info(f'No PDF candidate elements found for {rest_name} at {url}')
        return

    seen = set()
    for href in urls:
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
                 handle_runtime_pdf: bool = True, download_filename: str | None = None,
                 download_via_browser: bool = False, click_xpath=None, url_pattern=None):
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
        download_via_browser: Download direct PDF links through Chrome instead of requests
        click_xpath: Optional element to click before discovering links
        url_pattern: Optional regex for extracting links from rendered page source
    """
    # Create folder and configure driver to download into it when handling runtime PDFs
    path = create_folder(rest_name, getattr(dcw, 'folder', None))
    driver = setup_driver(download_dir=path if (handle_runtime_pdf or download_via_browser) else None)
    
    try:
        print(f'1. Source URL: {url}')
        
        print(f'2. Browsing: {url}')
        driver.get(url)
        sleep(wait_time)

        if click_xpath:
            triggers = driver.find_elements(By.XPATH, click_xpath)
            if not triggers:
                raise RuntimeError(f'No element found for click XPath: {click_xpath}')
            driver.execute_script("arguments[0].click();", triggers[0])
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
        links = []
        if url_pattern:
            print(f'3. Finding links in rendered page source: {url_pattern}')
            links = re.findall(url_pattern, driver.page_source)
        elif use_partial_link_text and partial_link_value:
            print(f'3. Finding elements by partial text: {partial_link_value}')
            elements = driver.find_elements(By.PARTIAL_LINK_TEXT, partial_link_value)
        elif xpath_:
            print(f'3. Finding elements by XPath: {xpath_}')
            elements = driver.find_elements(By.XPATH, xpath_)
        else:
            # Generic fallbacks commonly seen on Ten Kites
            print('3. Finding default PDF triggers (Download|PDF|Allergen)')
            elements = driver.find_elements(By.XPATH, "//a[contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'pdf') or contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'download') or contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'allergen')] | //button[contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'pdf') or contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'download') or contains(translate(., 'PDFDOWNLOADALLERGEN', 'pdfdownloadallergen'),'allergen')] ")

        print(f'4. Found {len(links) or len(elements)} potential PDF trigger(s)')

        # First try href-based downloads via requests
        for el in elements:
            href = el.get_attribute('href')
            if href:
                links.append(href)
        links = list(dict.fromkeys(links))

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
                if download_via_browser:
                    before = {f for f in os.listdir(path) if f.lower().endswith('.pdf')}
                    print(f'6.{i+1} Downloading in browser: {link}')
                    driver.get(link)
                    downloaded = wait_for_new_pdf(path, before_set=before, timeout=90)
                    if downloaded and downloaded != file_path:
                        os.replace(downloaded, file_path)
                    if downloaded:
                        print(f'6.{i+1} Saved browser download to: {file_path}')
                    else:
                        print(f'6.{i+1} Timed out waiting for browser PDF download')
                else:
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

    try:
        _navigate(driver)
        return driver
    except WebDriverException as e:
        msg = str(e)
        if ("Read timed out" in msg) or ("HTTPConnectionPool" in msg) or ("ERR_CONNECTION" in msg):
            # Restart the driver and retry once
            try:
                print("Transport timeout detected, restarting driver and retrying navigation…")
                driver.quit()
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
