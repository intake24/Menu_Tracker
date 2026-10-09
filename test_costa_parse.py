import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import define_collection_wave as dcw


def load_costa():
    """Import the digit-prefixed script without creating collection folders."""
    with tempfile.TemporaryDirectory() as tmp, \
            patch.object(dcw, "folder", tmp), \
            patch("helpers.create_folder", return_value=tmp):
        path = Path(__file__).parent / "food-chains" / "3_CostaCoffee_selenium.py"
        spec = importlib.util.spec_from_file_location("costa_selenium", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


costa = load_costa()


class CostaTableParsingTests(unittest.TestCase):
    def test_drink_nutrition_uses_header_columns(self):
        rows = [
            ["", "Per 100g/ml", "In Store (384ml)", "Take-Out (384ml)"],
            ["Energy (kJ)", "345", "1322", "1322"],
            ["Energy (kcal)", "82", "315", "312"],
        ]
        self.assertEqual(
            costa.parse_nutrition_rows(rows),
            {
                "Portion_Size": "384ml",
                "Energy (kJ)_Per 100g/ml": "345",
                "Energy (kJ)_In Store": "1322",
                "Energy (kJ)_Take-Out": "1322",
                "Energy (kcal)_Per 100g/ml": "82",
                "Energy (kcal)_In Store": "315",
                "Energy (kcal)_Take-Out": "312",
            },
        )

    def test_food_nutrition_single_portion_column(self):
        rows = [["", "Per 100g/ml", "Per Portion (100ml)"], ["Fat (g)", "11.7", "11.7"]]
        self.assertEqual(
            costa.parse_nutrition_rows(rows),
            {"Portion_Size": "100ml", "Fat (g)_Per 100g/ml": "11.7", "Fat (g)_Per Portion": "11.7"},
        )

    def test_allergen_rows_are_label_value_pairs(self):
        rows = [["Egg Products", "Yes"], ["Soya Products", "C"], ["", "ignored"]]
        self.assertEqual(
            costa.parse_allergen_rows(rows), {"Egg Products": "Yes", "Soya Products": "C"}
        )

    def test_empty_tables_give_empty_dicts(self):
        self.assertEqual(costa.parse_nutrition_rows([]), {})
        self.assertEqual(costa.parse_allergen_rows([]), {})


class CostaWedgedBrowserTests(unittest.TestCase):
    def test_failed_product_is_retried_in_a_fresh_browser(self):
        from unittest.mock import MagicMock
        wedged, fresh = MagicMock(name="wedged"), MagicMock(name="fresh")
        seen = []

        def extract(driver, url, category):
            seen.append(driver)
            if driver is wedged:
                raise RuntimeError("Timed out receiving message from renderer: 60.000")
            return {"Product_Name": "Matcha Latte"}

        with patch.object(costa, "setup_driver", side_effect=[wedged, fresh]), \
                patch.object(costa, "safe_get", side_effect=lambda d, *a, **k: d), \
                patch.object(costa, "try_click_accept_cookies"), \
                patch.object(costa, "sleep"), \
                patch.object(costa, "collect_product_urls", return_value={"u1": "Drinks"}), \
                patch.object(costa, "extract_product", side_effect=extract):
            items = costa.scrape_costa_menu()

        self.assertEqual(items, [{"Product_Name": "Matcha Latte"}])
        self.assertEqual(seen, [wedged, fresh])
        wedged.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
