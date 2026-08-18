# First 20 scraper summary

## Status

- Full serial smoke test: **20/20 passed, 0 failed** on 18 August 2026.
- PDF-chain follow-up: **6/6 passed** on 19 August 2026.
- Regression suite: **15 tests passed**.
- Results and evidence are ignored local artifacts; they are not committed.

## Outcomes

CSV counts exclude headers. JSON counts match their corresponding CSV unless
noted. PDF files have valid signatures and readable, relevant content.

| # | Chain | Validated output |
| ---: | --- | --- |
| 1 | McDonald's | 213 CSV rows; 164 source JSON files |
| 2 | Wetherspoons | 429 CSV rows; one source JSON response |
| 3 | Costa Coffee | 133 CSV/JSON records; 128 with energy |
| 4 | Greggs | 136 CSV/JSON records |
| 5 | KFC | 123 CSV/JSON records |
| 6 | Domino's | Four nutrition, ingredient, and allergen PDFs |
| 7 | Starbucks | Five 2026 nutrition and allergen PDFs |
| 8 | Pizza Hut | One dietary/nutrition/allergen PDF |
| 9 | Subway | Two dynamically discovered nutrition and allergen PDFs |
| 10 | Nando's | 132 CSV/JSON records; 131 with energy |
| 11 | PizzaExpress | 11 nutrition, ingredient, and allergen PDFs |
| 12 | Burger King | 332 CSV/JSON records; 321 with energy |
| 13 | Pret | 251 CSV/JSON records |
| 14 | Caffè Nero | 338 CSV/JSON records |
| 15 | Wagamama | 341 CSV/JSON records |
| 16 | Beefeater | 1,190 CSV/JSON records |
| 17 | Brewers Fayre | 1,586 CSV/JSON records |
| 18 | Sizzling Pubs | 300 CSV/JSON records; 253 with energy |
| 19 | Ember Inns | 341 CSV/JSON records |
| 20 | Chef & Brewer | 11 menu PDFs containing calorie values |

## What changed

- Added chains 1–20 and explicit output contracts to `scraper_manifest.json`.
- Made `Master_Compile.py` serial by default because Costa fails when browser
  scrapers overlap; concurrency remains available for known-safe subsets.
- Strengthened validation: CSV needs a header and data row, JSON must parse and
  be nonempty, and PDF must have a valid signature.
- Fixed Nando's stale Selenium elements, increasing output from seven to 132
  products.
- Replaced Starbucks's dead API workflow with current official PDF discovery.
- Narrowed Pizza Hut discovery so unrelated corporate PDFs cannot pass.
- Added runnable PDF wrappers for Pizza Hut, Subway, and PizzaExpress.
- Made Subway discover both current documents from its stable nutrition page;
  no dated PDF URL is pinned.
- Consolidated all six first-20 PDF chains onto `combo_PDFDownload` or
  `selenium_PDF`; removed bespoke Domino's and Chef & Brewer download flows.

## Verification

Full run:

```bash
python Master_Compile.py first20_collection \
  1_McDonalds.py 2_Wetherspoons.py 3_CostaCoffee_selenium.py \
  4_Greggs.py 5_KFC.py 6_Dominos.py 7_Starbucks.py 8_PizzaHut.py \
  9_Subway.py 10_Nandos.py 11_PizzaExpress.py 12_BurgerKing.py \
  13_Pret.py 14_CaffeNero.py 15_Wagamama.py 16_Beefeater.py \
  17_BrewersFayre.py 18_Sizzling.py 19_EmberInns.py 20_ChefBrewer.py
```

Successful data is written under `first20_collection/<chain>_<date>/`. Failed
scrapers write diagnostics under `evidence/<run-id>/<scraper>/`. See
[`COLLECTION_WORKFLOW.md`](COLLECTION_WORKFLOW.md) for operation and repair
instructions.

## Human decision remaining

The six PDF chains preserve authoritative source documents. Decide whether a
separate downstream phase should normalize them into CSV/JSON, and whether
PizzaExpress-associated Mac & Wings and QSR documents should remain in scope.
