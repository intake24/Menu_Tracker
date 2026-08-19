import importlib
import unittest


common_rooms = importlib.import_module("48_CommonRooms")


class CommonRoomsTests(unittest.TestCase):
    def test_discovers_successor_menu_and_parses_nutrition(self):
        landing = '<a href="https://menus.tenkites.com/current">Allergen and dietary information</a>'
        menu = """
          <section class="k10-course"><h2>Mains</h2>
            <div class="k10-l-grid">
              <span class="k10-recipe__name-val">Burger</span>
              <p class="k10-recipe__desc">With fries</p>
              <div class="k10-recipe__labels-wrapper-content">Milk</div>
              <div class="k10-recipe__nutrients-item"><span>Energy (kcal)</span><span>1,234</span></div>
            </div>
          </section>
        """

        self.assertEqual("https://menus.tenkites.com/current", common_rooms.discover_menu_url(landing))
        record = common_rooms.parse_menu(menu)[0]
        self.assertEqual(("Burger", "1234", ["Milk"]), (record["item_name"], record["kcal"], record["allergens"]))


if __name__ == "__main__":
    unittest.main()
