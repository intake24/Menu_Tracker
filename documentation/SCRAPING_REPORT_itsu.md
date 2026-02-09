# Walkthrough - Menu Tracker Improvements

Successfully improved the Costa Coffee scraper and rewrote the Itsu scraper to include allergens and detailed nutrition.

## Costa Coffee Improvements

- **Fixed Selenium Version Mismatch**: Dynamically detects the Chrome version to ensure compatibility with `undetected_chromedriver`.
- **Bypassed API Blocking**: Implemented a robust Selenium-only approach to extract data directly from the web interface when the GraphQL API is blocked.
- **Resolved Conflict Markers**: Cleaned up the `3_CostaCoffee.py` code to remove all merge conflict remnants.

## Itsu Scraper Rewrite

A comprehensive rewrite of `38_Itsu.py` was performed to meet the new requirement for allergen and nutritional data.

### Refinements (latest)
- **Improved Coverage**: Now iterates through sub-menu categories (Soups, Rice Bowls, etc.) using `a.btn.btn-light.btn-sm` to ensure no items are missed.
- **Improved Discovery**: Uses `a.base-lined-card.product-listing-card` for reliable product link collection.
- **Accurate Extraction**:
    - Fixed product description selector to `p.description`.
    - Improved allergen extraction by targeting `p.contain-info`.
    - Standardized nutrition mapping from `dl.nutrition-facts`.

### Verification (Expected Results)
The scraper generates `itsu_nutrition.csv` with the following header:
`collection_date,rest_name,menu_section,item_name,allergens,kj,kcal,fat,satfat,carb,sugar,protein,salt,description`

> [!NOTE]
> The Itsu website primarily displays kcal; kJ is calculated dynamically to ensure consistent data across all restaurants in the tracker.

---

!["Itsu Product Discovery"](itsu_exploration.webp)
*Recording of the exploration phase for the Itsu scraper rewrite.*
