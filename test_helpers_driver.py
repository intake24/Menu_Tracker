import subprocess
import unittest
from unittest.mock import MagicMock, patch

from urllib3.exceptions import ReadTimeoutError

from helpers import get_chrome_binary_and_version, safe_get


class ChromeDetectionTests(unittest.TestCase):
    @patch("helpers.subprocess.check_output", return_value="Chromium 150.0.7871.128")
    @patch(
        "helpers.shutil.which",
        side_effect=lambda name: "/usr/bin/chromium" if name == "chromium" else None,
    )
    def test_detects_chromium_when_google_chrome_is_absent(self, which, check_output):
        self.assertEqual(get_chrome_binary_and_version(), ("/usr/bin/chromium", 150))
        check_output.assert_called_once_with(
            ["/usr/bin/chromium", "--version"], text=True, stderr=subprocess.STDOUT
        )

    @patch("helpers.setup_driver")
    def test_safe_get_reuses_a_healthy_driver(self, setup_driver):
        driver = MagicMock()
        self.assertIs(safe_get(driver, "https://example.com"), driver)
        driver.get.assert_called_once_with("https://example.com")
        driver.quit.assert_not_called()
        setup_driver.assert_not_called()

    @patch("helpers.try_click_accept_cookies")
    @patch("helpers.set_driver_timeouts")
    @patch("helpers.setup_driver")
    def test_safe_get_restarts_when_chromedriver_hangs(self, setup_driver, *_):
        # A hung chromedriver surfaces as a raw urllib3 ReadTimeoutError, not a WebDriverException.
        hung = MagicMock()
        hung.get.side_effect = ReadTimeoutError(None, "/session", "Read timed out. (read timeout=120)")
        fresh = MagicMock()
        setup_driver.return_value = fresh
        self.assertIs(safe_get(hung, "https://example.com"), fresh)
        hung.quit.assert_called_once()
        fresh.get.assert_called_once_with("https://example.com")


if __name__ == "__main__":
    unittest.main()
