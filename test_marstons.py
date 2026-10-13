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
    def test_reloads_when_the_page_has_not_hydrated(self, sleep):
        driver = MagicMock()
        buttons = [MagicMock()]
        # attempt 1: cookie ok, buttons time out; attempt 2: cookie ok, buttons found
        with patch.object(marstons, "WebDriverWait",
                          waits(MagicMock(), TimeoutException(), MagicMock(), buttons)):
            self.assertEqual(marstons.load_menu_buttons(driver), buttons)
        self.assertEqual(driver.get.call_count, 2)

    @patch.object(marstons.time, "sleep")
    def test_raises_when_the_menus_never_appear(self, sleep):
        driver = MagicMock()
        with patch.object(marstons, "WebDriverWait", waits(*[TimeoutException()] * 6)):
            with self.assertRaises(RuntimeError):
                marstons.load_menu_buttons(driver)


if __name__ == "__main__":
    unittest.main()
