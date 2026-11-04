import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from selenium.common.exceptions import TimeoutException

import define_collection_wave as dcw


def load_harvester():
    """Import the digit-prefixed script without creating collection folders."""
    with tempfile.TemporaryDirectory() as tmp, \
            patch.object(dcw, "folder", tmp), \
            patch("helpers.create_folder", return_value=tmp):
        path = Path(__file__).parent / "food-chains" / "53_Harvester.py"
        spec = importlib.util.spec_from_file_location("harvester", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


harvester = load_harvester()


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


class LoadFoodCardsTests(unittest.TestCase):
    @patch.object(harvester, "safe_get", side_effect=lambda drv, url, **kw: drv)
    def test_retries_a_menu_whose_cards_time_out(self, safe_get):
        driver, cards = MagicMock(), [MagicMock()]
        with patch.object(harvester, "WebDriverWait", waits(TimeoutException(), cards)):
            self.assertEqual(harvester._load_food_cards(driver, "u"), (driver, cards))
        self.assertEqual(safe_get.call_count, 2)

    @patch.object(harvester, "safe_get", side_effect=lambda drv, url, **kw: drv)
    def test_returns_no_cards_after_the_last_attempt(self, safe_get):
        driver = MagicMock()
        with patch.object(harvester, "WebDriverWait", waits(*[TimeoutException()] * 3)):
            self.assertEqual(harvester._load_food_cards(driver, "u"), (driver, []))
        self.assertEqual(safe_get.call_count, 3)


class RequireMenusTests(unittest.TestCase):
    def test_raises_naming_menus_that_yielded_nothing(self):
        with self.assertRaisesRegex(RuntimeError, "mainmenu"):
            harvester._require_all_menus(["mainmenu"])

    def test_passes_when_every_menu_had_items(self):
        harvester._require_all_menus([])


if __name__ == "__main__":
    unittest.main()
