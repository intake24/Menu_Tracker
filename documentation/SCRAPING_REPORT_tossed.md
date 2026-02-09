# Scraping Report: TossedUK Rewrite

This report documents the rewrite of the TossedUK scraper (`80_tossed.py`) to handle the interactive VMOS ordering platform.

## Objective
The goal was to replace the legacy Tossed scraper with a new version capable of navigating the dynamic menu structure, opening item modals, and extracting nutritional data from the "Nutrition" tab.

## Technical Details

### Targeted Platform: VMOS
- **Base Store URL**: `https://tosseduk.vmos.io/store/...`
- **Architecture**: Single Page Application (SPA) with lazy-loaded item lists.

### Key Logic & Selectors
- **Category Traversal**: The script identifies all category links (e.g., "hot food", "salads") in the horizontal navigation list (`ul.e1cxpgmd8 a`).
- **Modal Interaction**:
    - **Trigger**: Clicks `button[aria-label='More details.']`.
    - **Navigation**: Clicks the "Nutrition" button (`#meal-tab-2`) inside the modal to reveal data.
- **Improved Item Data**:
    - **Name**: Scoped to the `h1` tag within the `.ReactModal__Content` to avoid landing page headers.
    - **Allergens**: Captured from the specific `div` with `id="allergens-text"`.
- **Nutrition Extraction**:
    - Scrapes the `innerText` of the nutritional container.
    - Maps labels like "Fats" and "of which saturates" to standardized CSV columns.
- **Resilience**:
    - Uses `execute_script` for clicks to avoid interception by hidden overlays.
    - Re-fetches button lists after each modal close to prevent stale element exceptions.
    - Includes automatic `Escape` key fallback to clear modals on failure.

## Verification
The site investigation confirmed that item-specific data is hidden behind the "More details" button. The scraper correctly:
1. Navigates to a category.
2. Scrolls to reveal all items.
3. Opens the modal for each item.
4. Switches to the Nutrition tab.
5. Captures and standardizes the data.

### Sample Structure Investigation (Media)
The following recording shows the modal structure and nutrition tab used for the selector logic.

![TossedUK Modal Inspection](tossed_inspection.webp)

## Conclusion
The rewritten `80_tossed.py` is ready for high-fidelity data collection. It follows the project standard for CSV/JSON outputs and correctly filters out items without nutritional details (like meal deals).
