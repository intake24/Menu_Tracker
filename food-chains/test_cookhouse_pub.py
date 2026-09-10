import importlib.util
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for helpers/define_collection_wave

spec = importlib.util.spec_from_file_location('cookhouse', Path(__file__).with_name('49_CookhousePub_obsolete.py'))
cookhouse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cookhouse)


class CookhousePubTests(unittest.TestCase):
    def test_discovers_menu_and_parses_recipe_without_placeholder(self):
        landing = BeautifulSoup(
            '<a href="/en-gb/allergy-nutrition/current-web">Current menu</a>', "html.parser"
        )
        menu = BeautifulSoup("""
            <details class="recipe" data-submenu="Mains" data-diet="vegan">
              <div class="title">Soup <span>VE</span></div>
              <div class="kv"><div class="block"><span class="v">Celery</span></div></div>
              <table><tr><td>Energy</td><td>420 kJ / 100 kcal</td></tr></table>
            </details>
            <details class="recipe"></details>
        """, "html.parser")

        with patch.object(cookhouse, "soup_for", side_effect=[landing, menu]):
            urls = cookhouse.menu_urls()
            records = cookhouse.parse_menu(urls[0])

        self.assertEqual(["https://www.cookhouseandpub.co.uk/en-gb/allergy-nutrition/current-web"], urls)
        self.assertEqual(1, len(records))
        self.assertEqual(("Soup", "100", "Celery"), (records[0]["item_name"], records[0]["kcal"], records[0]["allergens"]))


if __name__ == "__main__":
    unittest.main()
