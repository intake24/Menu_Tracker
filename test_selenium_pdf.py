import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import helpers


class _Link:
    def get_attribute(self, name):
        return '/guide.pdf' if name == 'href' else None


class _Driver:
    def __init__(self, download_dir):
        self.download_dir = Path(download_dir)
        self.urls = []
        self.page_source = ''
        self.clicked = False
        self.quit_called = False

    def get(self, url):
        self.urls.append(url)
        if url.endswith('/guide.pdf'):
            (self.download_dir / 'guide.pdf').write_bytes(b'%PDF-test')

    def find_elements(self, *_):
        return [_Link()]

    def execute_script(self, *_):
        self.clicked = True

    def quit(self):
        self.quit_called = True


class SeleniumPdfTests(unittest.TestCase):
    def test_browser_download_uses_the_browser_session_for_direct_pdf_links(self):
        # Catches a regression where a Selenium-discovered link is sent back to requests.
        with tempfile.TemporaryDirectory() as download_dir:
            driver = _Driver(download_dir)
            with patch.object(helpers, 'create_folder', return_value=download_dir), \
                 patch.object(helpers, 'setup_driver', return_value=driver), \
                 patch.object(helpers, 'PDFDownloader') as request_download:
                helpers.selenium_PDF(
                    'PapaJohns',
                    'https://example.test/allergens',
                    xpath_='//a',
                    prefix='https://example.test',
                    wait_time=0,
                    download_via_browser=True,
                )

            self.assertEqual(
                driver.urls,
                ['https://example.test/allergens', 'https://example.test/guide.pdf'],
            )
            self.assertTrue((Path(download_dir) / 'guide.pdf').is_file())
            self.assertTrue(driver.quit_called)
            request_download.assert_not_called()

    def test_clicks_then_extracts_links_from_rendered_page_source(self):
        with tempfile.TemporaryDirectory() as download_dir:
            driver = _Driver(download_dir)
            driver.page_source = 'https://cdn.test/menu-one https://cdn.test/menu-two'
            with patch.object(helpers, 'create_folder', return_value=download_dir), \
                 patch.object(helpers, 'setup_driver', return_value=driver), \
                 patch.object(helpers, 'PDFDownloader') as download:
                helpers.selenium_PDF(
                    'Restaurant',
                    'https://example.test/menu',
                    click_xpath='//button',
                    url_pattern=r'https://cdn\.test/menu-[a-z]+',
                    wait_time=0,
                )

            self.assertTrue(driver.clicked)
            self.assertEqual(2, download.call_count)


if __name__ == '__main__':
    unittest.main()
