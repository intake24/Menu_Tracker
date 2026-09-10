# MenuTracker Repository Instructions

MenuTracker is a Python-based web scraping and data collection system that automatically extracts nutritional information from UK food chain restaurant websites. This codebase uses multiple approaches—Selenium-based automation and direct API calls—to collect and standardize restaurant menu data.

## Architecture & Data Flow

**Collection Wave System**: The project is organized around quarterly data collection waves. `Master_Compile.py` creates the requested folder through `define_collection_wave.create_collection()`, exports it to scraper subprocesses, and runs the entries declared in `scraper_manifest.json`. `run_parallel.py` validates fresh outputs and records local evidence for failures. See `docs/COLLECTION_WORKFLOW.md`.

**Two Scraping Approaches** (all scripts live in `food-chains/`):
1. **Direct Scripts** (numbered files like `1_McDonalds.py`, `4_Greggs.py`): Simpler single-file scrapers for API endpoints or straightforward HTML pages. Import `create_folder()` from helpers to set output path.
2. **Selenium Automation** (e.g., `3_CostaCoffee_selenium.py`, `39_BenJerry_selenium.py`): Used when JavaScript rendering or bot-detection evasion is required. Uses `setup_driver()` from helpers for anti-detection configuration.

**Data Output**: All scrapers produce CSV files with standardized column names (e.g., `kcal`, `protein`, `carb`, `fat`, `menu_section`, `item_name`) saved to the collection folder. Some also create JSON files during processing for debugging.

**Chrome Driver Management**: The `setup_driver()` function in helpers.py attempts `undetected_chromedriver` first (better evasion), then falls back to Selenium Manager. It detects installed Chrome or Chromium and matches the driver version automatically.

## Setup & Dependencies

**Environment**:
- Requires Python 3.8+
- Install dependencies: `pip install -r requirements.txt`
- Key packages: `beautifulsoup4`, `selenium`, `pandas`, `lxml`, `requests`, `undetected-chromedriver`, `webdriver-manager`
- For Colab environments: the code detects `/content/drive/MyDrive` and sets paths accordingly (see `define_collection_wave.py`)

**Chrome Driver**: Selenium Manager resolves a compatible driver if `undetected_chromedriver` fails, but manual setup may still be needed for Colab.

## Running Scrapers

**Full Collection Wave**:
```bash
python Master_Compile.py Aug_collection_2026
```
This executes every manifest entry serially by default and validates all declared output contracts. Append exact manifest script names to run a subset; increase `--workers` only for a known-safe subset without competing Selenium sessions.

**Single Chain Scraper**:
```bash
# Run individual script (e.g., McDonald's) via Master_Compile.py so
# food-chains/ scripts can resolve their helpers.py import
python Master_Compile.py Aug_collection_2026 1_McDonalds.py
```

**Define Collection Wave When Running**: Pass the collection folder name to `Master_Compile.py`; do not edit or run `define_collection_wave.py` first.

**Resuming an Interrupted Wave**: `--resume` skips any script whose manifest-declared output already validates against the existing collection folder, and re-runs everything else (failed or never attempted). Omit the collection name to resume the most recently modified one:
```bash
python Master_Compile.py --resume                                   # resume latest, everything remaining
python Master_Compile.py Aug_collection_2026 --resume                # resume a specific wave
python Master_Compile.py Aug_collection_2026 --resume 1_McDonalds.py # resume a specific wave, specific scripts
```
Name the collection explicitly whenever also passing SCRIPT names without it, the first SCRIPT name is misread as the collection name (a Python 3.11 argparse limitation with `--resume` between two positionals — `parse_intermixed_args` fixes the ordering issue but not this specific omitted-collection case). If everything requested already succeeded, it prints a message and exits without running anything.

What a resume leaves behind, concretely:
- Scripts that already validated are never touched: no re-run, no changed files, their `evidence_log.json` entry stays exactly as the original run left it.
- `create_folder()` (helpers.py) names each chain's own subfolder `<rest_name>_<today's date>`, not the collection's original date. Resuming the *same calendar day* as the failed attempt overwrites that chain's partial output in place, clean. Resuming on a *later day* creates a new dated subfolder instead — the old broken one from the failed attempt is not deleted, just left orphaned alongside the new good one. Never-attempted chains that finally run on resume also get today's date, so one collection folder can end up with chain subfolders spanning several different dates even though it's nominally one wave.
- Evidence bundles (written only on failure, under `evidence_dir/<run_id>/<script>/`) get a fresh `run_id` per `Master_Compile.py` invocation. A chain that failed on the original run and fails again on resume ends up with two separate bundles, not one overwritten in place; if it succeeds on resume, the original failed bundle just stays there as stale history.

**Per-Script Timeout**: `--timeout` (seconds, default 2400) kills and marks failed any scraper still running past that. Default is a guess based on the slowest chain observed so far, not a measured ceiling — some legitimately take 20+ minutes (Selenium-heavy sites); tune it if you see false-positive timeouts.

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

**Error Handling**: Scrapers may fail if websites change. Update site-specific selectors when layout changes; the commit that fixes it is the record of what changed and why.

## Common Tasks

**Adding a New Restaurant Scraper**:
1. Inspect target website structure (note CSS classes, XPath patterns, if JavaScript-heavy)
2. Create a numbered script in `food-chains/` (e.g., `50_NewChain.py`) using BeautifulSoup or `requests` for simple API/static HTML
3. If JavaScript-rendered or bot-protected: use Selenium with `setup_driver()` from helpers
4. Ensure output CSV has all standard columns, save to `create_folder(name, folder)`
5. Test with a small subsection before adding to `Master_Compile.py`

**Debugging Site Changes**:
- Use `setup_driver()` headless=False to visually inspect what Selenium sees
- Test URL patterns with `requests.get()` first before writing full scraper

**Handling PDFs**: Use helpers like `combo_PDFDownload()` or `java_PDF()`. If extraction fails, fall back to Tabula or Camelot (mentioned in README) and save extracted CSVs to collection folder.

## Important Notes

- **Colab Compatibility**: Code detects Colab environment via `/content/drive/MyDrive`. Paths and Selenium setup adapt automatically. The jupyter notebook `menutracker.ipynb` provides Colab-specific workflow.
- **Rate Limiting**: Master_Compile.py and individual scrapers include delays to reduce load on target websites. Respect robots.txt and consider site load.
- **Data Standardization**: The Python workflow ends at validated chain-level outputs. Merging and standardization are a separate downstream phase.
- **Git Commits**: Fixes use format `fix(<chain>): <details>`, features use `feat(<chain>): <details>` for clear change tracking.
- **Versioning**: If a chain scraper becomes outdated but you want to preserve it, rename with `_obsolete` suffix rather than deleting.

## Debugging & Troubleshooting

- **Import Errors**: Scraper scripts live in `food-chains/` and import `helpers.py`/`define_collection_wave.py` from the repo root; running them via `Master_Compile.py` (or the Docker image, which sets `PYTHONPATH=/app`) resolves this automatically. Running a script directly needs `PYTHONPATH=<repo root>` set first.
- **Chrome Driver Fails**: Check Chrome or Chromium is installed; if `undetected_chromedriver` fails, the helper falls back to Selenium Manager
- **No Data Output**: Check that `folder` variable is set (run `define_collection_wave.py` first); verify URLs are accessible with manual requests/curl
- **XPath/Selector Issues**: Websites change frequently. Test selectors in browser dev tools before hardcoding.

## Issue tracking

Issues and PRDs use GitHub Issues in `intake24/Menu_Tracker`.
