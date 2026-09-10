import subprocess
import unittest
from unittest.mock import MagicMock, patch

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


if __name__ == "__main__":
    unittest.main()
