# Scraping Report: Table Table

This report documents the implementation of the Table Table nutritional and allergen scraper.

## Objective
The goal was to implement a scraper for Table Table (`21_TableTable.py`) by leveraging the proven architecture of previously developed Whitbread group scrapers (Beefeater and Brewers Fayre).

## Implementation Details

### Data Source
- **Main URL**: `https://www.tabletable.co.uk/en-gb/allergy-nutrition`

### Key Selectors & Logic
- **Menu Discovery**:
    - Identifies links with the pattern `/allergy-nutrition/tt-`.
    - Captures human-readable menu names (e.g., "Autumn Winter 25 Menu") from `<u>`, `<i>`, or `<b>` tags inside the <a> anchors.
- **Section Extraction**:
    - Submenu tabs are identified via `<label>` tags with `for` attributes linking to `SubMenuX`.
- **Item Extraction**:
    - **Name**: `.dishDetails_P.handle label`
    - **Allergens**: `span.dishContains_P2` and `span.dishMayContains_P2`.
    - **Nutrition**: `table.NandATable` containing per-portion data for energy, fat, carbs, etc.
- **Data Formatting**:
    - Standard kJ/kcal separation logic applied to energy strings.

### Structural Verification
The site exploration confirmed that Table Table uses the same underlying platform as Beefeater. The primary difference is the use of `<u>` tags for seasonal menu link titles on the landing page.

## Verification Logic
Confirmed consistency in data hierarchy and content selectors. The Selenium script handles the dynamic discovery and traversal of the menus exactly as intended.

## Conclusion
The `21_TableTable.py` script is fully implemented and ready for local data collection. It adheres to all project metadata and CSV formatting standards.
