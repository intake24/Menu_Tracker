# MenuTracker Repository Instructions

MenuTracker is a Python-based web scraping and data collection system that automatically extracts nutritional information from UK food chain restaurant websites. This codebase uses multiple approaches—Scrapy spiders, Selenium-based automation, and direct API calls—to collect and standardize restaurant menu data.

## Architecture & Data Flow

**Collection Wave System**: The project is organized around quarterly data collection waves. `Master_Compile.py` creates the requested folder through `define_collection_wave.create_collection()`, exports it to scraper subprocesses, and runs the entries declared in `scraper_manifest.json`. `run_parallel.py` validates fresh outputs and records local evidence for failures. See `docs/COLLECTION_WORKFLOW.md`.

**Three Scraping Approaches**:
1. **Scrapy Spiders** (`Scrapy_spiders/` directory): Full-featured web crawlers for complex sites with multiple pages or menu sections. Each spider is a class inheriting from `scrapy.Spider` with XPath selectors for HTML parsing.
2. **Direct Scripts** (numbered files like `1_McDonalds.py`, `4_Greggs.py`): Simpler single-file scrapers for API endpoints or straightforward HTML pages. Import `create_folder()` from helpers to set output path.
3. **Selenium Automation** (e.g., `3_CostaCoffee_selenium.py`, `39_BenJerry_selenium.py`): Used when JavaScript rendering or bot-detection evasion is required. Uses `setup_driver()` from helpers for anti-detection configuration.

**Data Output**: All scrapers produce CSV files with standardized column names (e.g., `kcal`, `protein`, `carb`, `fat`, `menu_section`, `item_name`) saved to the collection folder. Some also create JSON files during processing for debugging.

**Chrome Driver Management**: The `setup_driver()` function in helpers.py attempts `undetected_chromedriver` first (better evasion), then falls back to Selenium Manager. It detects installed Chrome or Chromium and matches the driver version automatically.

## Setup & Dependencies

**Environment**:
- Requires Python 3.8+
- Install dependencies: `pip install -r requirements.txt`
- Key packages: `beautifulsoup4`, `scrapy`, `selenium`, `pandas`, `lxml`, `requests`, `undetected-chromedriver`, `webdriver-manager`
- For Colab environments: the code detects `/content/drive/MyDrive` and sets paths accordingly (see `define_collection_wave.py`)

**Chrome Driver**: Selenium Manager resolves a compatible driver if `undetected_chromedriver` fails, but manual setup may still be needed for Colab.

## Running Scrapers

**Full Collection Wave**:
```bash
python Master_Compile.py Aug_collection_2026
```
This executes every manifest entry concurrently and validates all declared output contracts. Append exact manifest script names to run a subset.

**Single Chain Scraper**:
```bash
# Run individual script (e.g., McDonald's)
python 1_McDonalds.py

# Run Scrapy spider (e.g., Nandos)
scrapy crawl 10_Nandos -a output_folder=<path>
```

**Define Collection Wave When Running**: Pass the collection folder name to `Master_Compile.py`; do not edit or run `define_collection_wave.py` first.

## Key Conventions

**Naming**: Numbered files indicate chain priority/order. Suffixes indicate scraping method:
- `_selenium`: Uses Selenium for JavaScript-heavy or bot-protected sites
- `_old` / `_obsolete`: Deprecated versions (don't use unless debugging)
- `_v2`: Revised version of existing scraper

**Helper Functions** (from `helpers.py`):
- `create_folder(name, folder)`: Create output directory, return path
- `combo_PDFDownload()`: Download PDFs with a given URL pattern, auto-extracts if possible
- `java_PDF()`: Handle Java-rendered PDFs
- `setup_driver()`: Create Chrome WebDriver with anti-bot features
- `RunSpider(spider_name, folder)`: Execute a Scrapy spider
- `RunScript(script_name)`: Execute a direct Python script

**Data Schema**: All outputs should include these columns where available:
- `collection_date`: ISO or "MMM-DD-YYYY" format
- `rest_name`: Restaurant name (consistent across waves)
- `menu_section`: Category/section of menu
- `item_name`: Dish name
- `item_description`: Full description
- `serving_size` / `servingsize`: Portion size
- `servingsizeunit`: Unit of measure (g, ml, etc.)
- Nutrients: `kcal`, `protein`, `carb`, `fat`, `satfat`, `sugar`, `fibre`, `salt` (and `_100` per 100g variants)
- `allergens`: List or comma-separated string

**User-Agent & Headers**: Scrapers use `fake_useragent` for rotating user agents and custom headers defined in helpers.py. This reduces bot-detection rate. Selenium-based scripts use `undetected_chromedriver` for additional evasion.

**Error Handling**: Scrapers may fail if websites change. Check `documentation/SCRAPING_REPORT_*.md` files for known issues and site structure notes. Update site-specific selectors when layout changes.

## Common Tasks

**Adding a New Restaurant Scraper**:
1. Inspect target website structure (note CSS classes, XPath patterns, if JavaScript-heavy)
2. If simple API or static HTML: create numbered script in root (e.g., `50_NewChain.py`) using BeautifulSoup or `requests`
3. If complex multi-page navigation: create Scrapy spider in `Scrapy_spiders/Scrapy_spiders/spiders/`
4. If JavaScript-rendered or bot-protected: use Selenium with `setup_driver()` from helpers
5. Ensure output CSV has all standard columns, save to `create_folder(name, folder)`
6. Test with a small subsection before adding to `Master_Compile.py`
7. If scraper becomes difficult to maintain, document site structure in `documentation/SCRAPING_REPORT_<chain>.md`

**Debugging Site Changes**:
- Check `documentation/` for existing scraping notes
- Use `setup_driver()` headless=False to visually inspect what Selenium sees
- For Scrapy spiders, print intermediate XPath results or use `-a output_folder=.` to save JSON artifacts
- Test URL patterns with `requests.get()` first before writing full scraper

**Handling PDFs**: Use helpers like `combo_PDFDownload()` or `java_PDF()`. If extraction fails, fall back to Tabula or Camelot (mentioned in README) and save extracted CSVs to collection folder.

## Important Notes

- **Colab Compatibility**: Code detects Colab environment via `/content/drive/MyDrive`. Paths and Selenium setup adapt automatically. The jupyter notebook `menutracker.ipynb` provides Colab-specific workflow.
- **Rate Limiting**: Master_Compile.py and individual scrapers include delays to reduce load on target websites. Respect robots.txt and consider site load.
- **Data Standardization**: The Python workflow ends at validated chain-level outputs. Merging and standardization are a separate downstream phase.
- **Git Commits**: Fixes use format `fix(<chain>): <details>`, features use `feat(<chain>): <details>` for clear change tracking.
- **Versioning**: If a chain scraper becomes outdated but you want to preserve it, rename with `_obsolete` suffix rather than deleting.

## Debugging & Troubleshooting

- **Import Errors**: Ensure `helpers.py` and `define_collection_wave.py` are in same directory as scraper scripts and Scrapy project
- **Chrome Driver Fails**: Check Chrome or Chromium is installed; if `undetected_chromedriver` fails, the helper falls back to Selenium Manager
- **No Data Output**: Check that `folder` variable is set (run `define_collection_wave.py` first); verify URLs are accessible with manual requests/curl
- **XPath/Selector Issues**: Websites change frequently. Test selectors in browser dev tools before hardcoding. Consider storing site HTML snapshots in `documentation/` for reference

## Agent skills

### Issue tracker

Issues and PRDs use GitHub Issues in `intake24/Menu_Tracker`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five-role label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository. See `docs/agents/domain.md`.
