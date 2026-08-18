import importlib.util
import tempfile
import unittest
from pathlib import Path

import define_collection_wave as dcw


FIXTURE = '''
<html><body>
  <a href="https://cdn.example.test/nutrition.pdf">Nutrition</a>
  <a href="/assets/allergens.pdf">Allergens</a>
  <a href="https://cdn.example.test/nutrition.pdf">Duplicate</a>
  <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Menu",
      "name": "Full Menu",
      "hasMenuSection": [{
        "@type": "MenuSection",
        "name": "Pizza",
        "hasMenuItem": [{
          "@type": "MenuItem",
          "name": "Margherita",
          "description": "Tomato. Mozzarella. Fresh basil.",
          "offers": {"@type": "Offer", "price": "10.50", "priceCurrency": "GBP"},
          "nutrition": {"@type": "NutritionInformation", "calories": "899 calories"},
          "suitableForDiet": ["https://schema.org/VegetarianDiet"]
        }],
        "hasMenuSection": [{
          "@type": "MenuSection",
          "name": "Vegan",
          "hasMenuItem": [{
            "@type": "MenuItem",
            "name": "Vegan Margherita",
            "nutrition": {"@type": "NutritionInformation", "calories": "700 calories"}
          }]
        }]
      }]
    }
  </script>
</body></html>
'''


class ZizziExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.collection = tempfile.TemporaryDirectory()
        cls.original_folder = dcw.folder
        dcw.folder = cls.collection.name
        spec = importlib.util.spec_from_file_location('zizzi', Path(__file__).with_name('24_Zizzi.py'))
        cls.zizzi = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.zizzi)

    @classmethod
    def tearDownClass(cls):
        dcw.folder = cls.original_folder
        cls.collection.cleanup()

    def test_extracts_unique_pdfs_and_jsonld_menu_items_with_calories(self):
        # Catches a return to the retired js-menus/WordPress-only extractor.
        self.assertEqual(
            self.zizzi.extract_pdf_urls(FIXTURE),
            [
                'https://cdn.example.test/nutrition.pdf',
                'https://www.zizzi.co.uk/assets/allergens.pdf',
            ],
        )

        records = self.zizzi.extract_menu_records(FIXTURE, collection_date='Aug-18-2026')

        self.assertEqual(len(records), 2)
        self.assertEqual(
            records[0],
            {
                'collection_date': 'Aug-18-2026',
                'rest_name': 'Zizzi',
                'menu_name': 'Full Menu',
                'menu_section': 'Pizza',
                'item_name': 'Margherita',
                'item_id': None,
                'kcal': '899 calories',
                'item_description': 'Tomato. Mozzarella. Fresh basil.',
                'price': '£10.50',
                'dietary': 'VegetarianDiet',
            },
        )
        self.assertEqual(records[1]['menu_section'], 'Pizza')
        self.assertEqual(records[1]['menu_sub_section'], 'Vegan')
        self.assertEqual(records[1]['kcal'], '700 calories')


if __name__ == '__main__':
    unittest.main()
