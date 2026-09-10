import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for helpers/define_collection_wave

import define_collection_wave as dcw


HOME_HTML = '''
<nav>
  <a href="/order-online/cakes">Cakes</a>
  <a href="/order-online/bread">Bread</a>
  <a href="/our-stores">Stores</a>
</nav>
'''

CATEGORY_HTML = '''
<div class="product-item"><a href="/pink-fraisier">Pink Fraisier</a></div>
<div class="product-item"><a href="/pink-fraisier">Image</a></div>
<div class="product-item"><a href="/croissant">Croissant</a></div>
<a class="pages-item-next" href="/order-online/cakes?p=2">Next</a>
'''

FINAL_CATEGORY_HTML = '''
<a class="pages-item-next" href="/order-online/cakes" aria-disabled="true">Next</a>
'''

PRODUCT_HTML = '''
<h1 class="product-title">Pink Fraisier</h1>
<div itemprop="description">Strawberry cake</div>
<span class="price">£46.00</span>
<details>
  <summary>Nutritional Information</summary>
  <table>
    <tr><th>Typical values</th><th>Per 120g serving</th><th>Per 100g</th></tr>
    <tr><td>Energy (kcal)</td><td>321</td><td>265</td></tr>
    <tr><td>Protein (g)</td><td>4.8</td><td>3.9</td></tr>
  </table>
</details>
<details>
  <summary>Allergens and Dietary Information</summary>
  <div class="allergens-new"><ul><li>Milk</li><li>Egg</li></ul></div>
</details>
'''


class PaulScraperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collection = tempfile.TemporaryDirectory()
        cls.original_folder = dcw.folder
        dcw.folder = cls.collection.name
        spec = importlib.util.spec_from_file_location('paul', Path(__file__).with_name('33_Paul.py'))
        cls.paul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.paul)

    @classmethod
    def tearDownClass(cls):
        dcw.folder = cls.original_folder
        cls.collection.cleanup()

    def test_current_markup_yields_categories_products_and_item_details(self):
        # Catches a return to PAUL's retired category-item and hide-desk markup.
        self.assertEqual(
            self.paul.get_category_links(HOME_HTML),
            [
                'https://www.paul-uk.com/order-online/cakes',
                'https://www.paul-uk.com/order-online/bread',
            ],
        )
        self.assertEqual(
            self.paul.get_product_links_and_next(
                CATEGORY_HTML, 'https://www.paul-uk.com/order-online/cakes'
            ),
            (
                [
                    'https://www.paul-uk.com/pink-fraisier',
                    'https://www.paul-uk.com/croissant',
                ],
                'https://www.paul-uk.com/order-online/cakes?p=2',
            ),
        )
        self.assertEqual(
            self.paul.get_product_links_and_next(
                FINAL_CATEGORY_HTML, 'https://www.paul-uk.com/order-online/cakes?p=3'
            ),
            ([], None),
        )
        with patch.object(self.paul, 'fetch_html', return_value=PRODUCT_HTML):
            item = self.paul.parse_product('https://www.paul-uk.com/pink-fraisier')

        self.assertEqual(item['item_name'], 'Pink Fraisier')
        self.assertEqual(item['item_desc'], 'Strawberry cake')
        self.assertEqual(item['price'], '£46.00')
        self.assertEqual(item['Energy (kcal)'], '321')
        self.assertEqual(item['Energy (kcal)_100g'], '265')
        self.assertEqual(item['servingsize'], ['120'])
        self.assertEqual(item['allergen'], {'present': ['Milk', 'Egg']})


if __name__ == '__main__':
    unittest.main()
