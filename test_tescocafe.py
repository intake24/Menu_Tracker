import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import define_collection_wave as dcw


def load_tesco():
    """Import the digit-prefixed script without creating collection folders."""
    with tempfile.TemporaryDirectory() as tmp, \
            patch.object(dcw, "folder", tmp), \
            patch("helpers.create_folder", return_value=tmp):
        path = Path(__file__).parent / "food-chains" / "69_TescoCafe.py"
        spec = importlib.util.spec_from_file_location("tescocafe", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


tesco = load_tesco()


class KcalFromPdfTests(unittest.TestCase):
    def test_key_ignores_diet_tags_and_ampersand(self):
        self.assertEqual(tesco._key("Black Forest French Toast (v)"), tesco._key("Black Forest French Toast"))
        self.assertEqual(tesco._key("Mac & Cheese"), tesco._key("Mac and Cheese"))

    def test_fill_kcal_only_fills_empty_exact_matches(self):
        items = [
            {"item_name": "Fish Finger Wrap", "kcal": ""},
            {"item_name": "Latte", "kcal": ""},
            {"item_name": "Already Set", "kcal": "100kcal"},
        ]
        table = {"fish finger wrap": "470kcal", "already set": "999kcal"}
        with patch.object(tesco, "pdf_kcal", return_value=table):
            tesco.fill_kcal(items, "x.pdf")
        self.assertEqual([i["kcal"] for i in items], ["470kcal", "", "100kcal"])


if __name__ == "__main__":
    unittest.main()
