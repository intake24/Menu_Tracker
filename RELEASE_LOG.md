# Release log

Newest first. One section per day; one line per food chain touched.
Add an entry here whenever a scraper, the manifest or a shared helper changes.

## 2026-10-10

Found by the first manual run of the 2026-10-09 fixes on dm-build.

- Runner (`run_parallel.py`): a script timeout crashed the whole run with `TypeError: can't concat str to bytes`
  (Python returns partial output as bytes on timeout), so no evidence or summary was written. Now decoded.
- 3 Costa Coffee: Chrome's renderer sometimes wedges mid-run ("Timed out receiving message from renderer");
  the old loop kept using that browser and each later page took about 3 minutes, so runs hit the 2400 s timeout.
  A failed product is now retried once in a fresh browser. Verified through `Master_Compile` on dm-build: 137 products in 630 s.

## 2026-10-09

Triage of the 2026-10-05 weekly run (72 of 81 scripts passed, 9 failed) plus
the dead-URL repairs for three pub chains.

### Shared code

- `helpers.safe_get`: imported the missing `TimeoutException` / `WebDriverException`
  (any failed navigation used to raise `NameError`, affecting 10 chains) and now
  also recovers from the raw urllib3 error a hung chromedriver raises.
  Regression test in `test_helpers_driver.py`.

### Fixed or adapted, by chain

| # | Chain | Change |
|---|-------|--------|
| 3 | Costa Coffee | Rewritten for the redesigned site (product pages are now separate links). Collects 136 products: 131 nutrition, 115 allergens, 78 ingredients. 5 snacks have no nutrition table on the site. Runs about 15 min. Parser tests in `test_costa_parse.py`. |
| 16 | Beefeater | Retired (`16_Beefeater_obsolete.py`): site now redirects to Premier Inn. Removed from manifest. |
| 24 | Zizzi | Manifest only: dropped the `*.pdf` expectation; the script collects data files, not a PDF. |
| 46 | Cineworld | Manifest only: output glob changed to `46_Cineworld_*/*.pdf` to match the real filenames. |
| 48 | Common Rooms | Retired (`48_CommonRooms_obsolete.py`): Social Pub & Kitchen publishes no allergen or nutrition data. Removed from manifest. |
| 51 | Farmhouse Inns | Dead PDF ID replaced by `combo_PDFDownload` on the pub allergens page (`keyword="sitecorecontenthub"`). Coverage is now the drink-allergen guide only (accepted). |
| 54 | Hungry Horse | Rewritten, requests only: menu JSON API for kcal/price, SmartChef pages for allergens. Writes `hungryhorse_nutrition.{json,csv}` (350 rows) and `hungryhorse_allergens.{json,csv}` (586 rows). Manifest outputs updated. |
| 57 | Greene King | Same fix as Farmhouse Inns, via the Silver Cross allergens page. |
| 59 | Odeon | PDF links render about 2 s after load; now polls up to 30 s instead of reading the page once. |
| 69 | Tesco Cafe | Intermittent bot-block page: retries up to 3 times with a fresh browser and backoff, and raises instead of writing an empty result. Still can fail on the server IP. |
| 78 | Birds Bakery | Selenium fallback now goes through `safe_get`, so a hung browser is restarted (154 records). |
| 85 | Real Greek | Returned 0 items on the server but 53 locally. Now prints diagnostics and raises on an empty result. Root cause looks environmental (IP). |

### Repo and tooling

- `scraper_manifest.json`: 79 entries after the changes above.
- `menutracker.ipynb`: normalized with nbstripout, run output removed; remarks added for the chains above.
- `test_notebook_clean.py` and a pre-commit nbstripout hook block committed notebook output.
- `scripts/run_collection.sh`: lock file name uses `$(id -un)` instead of `${USER}`.
- `scraping_urls.txt`: closed chains marked, Costa URL pattern added.

### Known open items

- Tesco Cafe and Real Greek may still fail from the production server.
- Farmhouse Inns / Greene King cover less than the old links did.
- Old run logs remain in git history before the notebook cleanup.
