import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import TimeoutException

import define_collection_wave as dcw


def load_marstons():
    """Import the digit-prefixed script without creating collection folders."""
    with tempfile.TemporaryDirectory() as tmp, \
            patch.object(dcw, "folder", tmp), \
            patch("helpers.create_folder", return_value=tmp):
        path = Path(__file__).parent / "food-chains" / "60_Marstons.py"
        spec = importlib.util.spec_from_file_location("marstons", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


marstons = load_marstons()


def waits(*outcomes):
    """WebDriverWait stand-in whose .until() yields each outcome in turn."""
    seq = iter(outcomes)

    def until(_condition):
        out = next(seq)
        if isinstance(out, Exception):
            raise out
        return out

    wait = MagicMock()
    wait.until.side_effect = until
    return MagicMock(return_value=wait)


class LoadMenuButtonsTests(unittest.TestCase):
    @patch.object(marstons.time, "sleep")
    @patch.object(marstons, "setup_driver")
    def test_restarts_the_browser_after_a_blocked_load(self, setup_driver, sleep):
        blocked, fresh = MagicMock(title="ERROR: The request could not be satisfied"), MagicMock()
        setup_driver.return_value = fresh
        buttons = [MagicMock()]
        # blocked browser: cookie + buttons time out; fresh browser: cookie ok, buttons found
        with patch.object(marstons, "WebDriverWait",
                          waits(TimeoutException(), TimeoutException(), MagicMock(), buttons)):
            self.assertEqual(marstons.load_menu_buttons(blocked), (fresh, buttons))
        blocked.quit.assert_called_once()
        fresh.get.assert_called_once()
        sleep.assert_any_call(30)

    @patch.object(marstons.time, "sleep")
    @patch.object(marstons, "setup_driver")
    def test_raises_with_the_page_title_when_the_menus_never_appear(self, setup_driver, sleep):
        driver = MagicMock(title="ERROR: The request could not be satisfied")
        setup_driver.return_value = driver
        with patch.object(marstons, "WebDriverWait", waits(*[TimeoutException()] * 8)):
            with self.assertRaisesRegex(RuntimeError, "request could not be satisfied"):
                marstons.load_menu_buttons(driver)
        self.assertEqual(setup_driver.call_count, 3)
        sleep.assert_any_call(90)


if __name__ == "__main__":
    unittest.main()
