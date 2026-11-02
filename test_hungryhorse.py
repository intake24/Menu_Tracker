import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import define_collection_wave as dcw


def load_hungryhorse():
    """Import the digit-prefixed script without creating collection folders."""
    with tempfile.TemporaryDirectory() as tmp, \
            patch.object(dcw, "folder", tmp), \
            patch("helpers.create_folder", return_value=tmp):
        path = Path(__file__).parent / "food-chains" / "54_HungryHorse.py"
        spec = importlib.util.spec_from_file_location("hungryhorse", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


hh = load_hungryhorse()

PRODUCT = {"name": "Soup", "portions": [{"name": "Standard", "calories": 336, "price": 4.29}]}
FULL = [
    {"name": "Main Menu", "categories": [{"name": "Starters", "products": [PRODUCT]}]},
    {"name": "Kids", "categories": [{"name": "Kids", "products": [PRODUCT]}]},
]
COLD = [FULL[0], {"name": "Kids", "categories": None}]


def response(payload):
    res = MagicMock()
    res.json.return_value = payload
    return res


class CollectNutritionTests(unittest.TestCase):
    @patch.object(hh, "_get")
    def test_skips_and_logs_menus_the_api_returns_without_categories(self, get):
        get.return_value = response(COLD)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rows = hh.collect_nutrition()
        self.assertEqual({r["menu"] for r in rows}, {"Main Menu"})
        self.assertIn("Kids", out.getvalue())
        self.assertEqual(get.call_count, 1)

    @patch.object(hh, "_get")
    def test_fails_when_the_main_menu_has_no_categories(self, get):
        get.return_value = response([{"name": "Main Menu", "categories": None}, FULL[1]])
        with self.assertRaisesRegex(RuntimeError, "Main Menu"):
            hh.collect_nutrition()


if __name__ == "__main__":
    unittest.main()
