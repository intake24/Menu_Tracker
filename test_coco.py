import importlib
import unittest


coco = importlib.import_module('84_Coco')


class CocoTests(unittest.TestCase):
    def test_build_records_from_menu_json_ld(self):
        html = '''
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Menu","hasMenuSection":[
          {"@type":"MenuSection","name":"PASTA","hasMenuItem":[
            {"@type":"MenuItem","name":"Pasta","description":"Tomato sauce",
             "offers":{"@type":"Offer","price":"8.95","priceCurrency":"GBP"},
             "suitableForDiet":["https://schema.org/VeganDiet","https://schema.org/VegetarianDiet"],
             "nutrition":{"@type":"NutritionInformation","calories":"271 calories"}}
          ]}
        ]}
        </script>
        '''

        records = coco.build_records_from_menu_json_ld(html)

        self.assertEqual(records, [{
            'collection_date': coco.date.today().strftime('%b-%d-%Y'),
            'rest_name': coco.REST_NAME,
            'menu_name': 'Coco Di Mama Menu',
            'menu_section': 'PASTA',
            'item_name': 'Pasta',
            'item_id': None,
            'kcal': '271 calories',
            'item_description': 'Tomato sauce',
            'price': '8.95',
            'dietary': 'VeganDiet, VegetarianDiet',
        }])


if __name__ == '__main__':
    unittest.main()
