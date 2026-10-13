import importlib.util
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
    {"name": "Main", "categories": [{"name": "Starters", "products": [PRODUCT]}]},
    {"name": "Kids", "categories": [{"name": "Kids", "products": [PRODUCT]}]},
]
COLD = [FULL[0], {"name": "Kids", "categories": None}]


def response(payload):
    res = MagicMock()
    res.json.return_value = payload
    return res


class CollectNutritionTests(unittest.TestCase):
    @patch.object(hh.time, "sleep")
    @patch.object(hh, "_get")
    def test_retries_when_a_cold_api_returns_null_categories(self, get, sleep):
        get.side_effect = [response(COLD), response(FULL)]
        rows = hh.collect_nutrition()
        self.assertEqual({r["menu"] for r in rows}, {"Main", "Kids"})
        self.assertEqual(get.call_count, 2)

    @patch.object(hh.time, "sleep")
    @patch.object(hh, "_get")
    def test_fails_loudly_rather_than_shipping_a_partial_menu(self, get, sleep):
        get.return_value = response(COLD)
        with self.assertRaisesRegex(RuntimeError, "Kids"):
            hh.collect_nutrition()


if __name__ == "__main__":
    unittest.main()
