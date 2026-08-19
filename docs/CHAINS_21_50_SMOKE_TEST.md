# Chains 21–50 scraper summary

## Status

- Accepted runners: **27/27 supported scripts passed, 0 failed** on 19 August
  2026 (the 26-runner serial acceptance plus a focused Common Room rerun).
- Coverage: 26 supportable chain IDs plus the separate YO! Sushi Tesco feed.
- Outputs: **5,418 matching CSV/JSON rows** and **18 valid, readable PDFs**.
- Four chains remain outside the manifest because no current authoritative
  online source is available; they are listed under human decisions.
- Regression suite: **17 tests passed**. Generated data and evidence remain
  ignored local artifacts.

## Outcomes

CSV counts exclude headers. Every structured CSV count matches its JSON count,
and all 5,418 records have a name.

| # | Chain | Validated outcome |
| ---: | --- | --- |
| 21 | Table Table | 966 records; all with energy and allergens |
| 22 | Toby Carvery | 197 records; 151 with energy |
| 23 | Revolution | Human-limited; current allergen service is unreachable locally |
| 24 | Zizzi | 586 records plus five current menu/nutrition PDFs |
| 25 | ASK Italian | 184 records plus two current allergen PDFs |
| 26 | Papa Johns | One dynamically discovered nutrition PDF |
| 27 | Yates | 208 records; 198 with energy |
| 28 | YO! Sushi | 691 records plus 65 Tesco-kiosk records; all with energy |
| 29 | All Bar One | 43 records; all with energy and 39 with allergens |
| 30 | GBK | 268 records; 239 with energy |
| 31 | Flaming Grill | Two current nutrition/NGCI PDFs |
| 32 | Loch Fyne | Retired; Greene King ceased trading the restaurant brand in 2023 |
| 33 | PAUL | 88 records; 81 with energy |
| 34 | Wimpy | 58 records; all with energy |
| 35 | Krispy Kreme | One current 62-page allergen/nutrition PDF |
| 36 | Bill's | 655 named records; all with energy |
| 37 | Walkabout | 112 records; all with energy |
| 38 | itsu | 133 records; 129 with energy |
| 39 | Ben & Jerry's | 43 records; 38 nutrition images with OCR, 32 containing kcal text |
| 40 | Asda Café | Human-limited; current data is available only in local cafés |
| 41 | Barburrito | 194 records; all with energy |
| 42 | Benugo | 66 records; 65 with energy |
| 43 | Boost Juice | 60 records; all with calories |
| 44 | Boswell | Three food, drink, and allergen PDFs |
| 45 | Brewhouse & Kitchen | One current allergen/nutrition matrix |
| 46 | Cineworld | One current allergen/nutrition guide |
| 47 | Coffee #1 | Two current food and beverage guides |
| 48 | Common Rooms | 146 successor records; all with energy and 117 with allergens |
| 49 | Cookhouse & Pub | 655 records; all with energy and allergens |
| 50 | Crussh | Human-limited; official site no longer publishes a menu |

## What changed

- Registered all 27 supportable scripts with explicit output contracts in
  `scraper_manifest.json`.
- Added dynamic PDF runners for Papa Johns, Boswell, Brewhouse & Kitchen,
  Cineworld, and Coffee #1.
- Replaced Flaming Grill and Krispy Kreme's pinned document URLs with dynamic
  discovery from stable official pages.
- Updated All Bar One to its current `/foodmenu` flow and made fatal browser
  failures return nonzero instead of silently succeeding.
- Added JSON output and overwrite-safe collection behaviour to GBK and Ben &
  Jerry's.
- Filtered 19 nameless Bill's placeholder fragments.
- Preserved Ben & Jerry nutrition-image URLs and added optional local
  Tesseract OCR because the current site no longer publishes nutrition text.
- Corrected Boost Juice's calorie field label.
- Followed Stonegate's documented Common Room rebrand into Social Pub &
  Kitchen and added dynamic discovery of its current Ten Kites nutrition
  portal, plus a parser regression test.
- Added a live Cookhouse & Pub HTML scraper covering both current official DOM
  variants, plus a deterministic parser regression test.
- Made Crussh fail clearly when its official site has no menu, rather than
  writing empty CSV/JSON files that resemble a successful scrape.
- Removed Revolution's dead Selenium flow. Its replacement checks official
  media dynamically, but Revolution remains excluded because the current food
  PDF is not an acceptable substitute for allergen/nutrition data.

## Verification

The accepted set can be rerun serially with the authoritative manifest:

```bash
python Master_Compile.py chains21_50_collection \
  21_TableTable.py 22_TobyCarvery.py 24_Zizzi.py 25_Ask.py \
  26_PapaJohns.py 27_Yates.py 28_Yosushi.py 28_Yosushi_Tesco.py \
  29_AllBarOne.py 30_GBK.py 31_FlamingGrill.py 33_Paul.py \
  34_Wimpy.py 35_krispyKreme.py 36_Bills.py 37_Walkabout.py \
  38_Itsu.py 39_BenJerry_selenium.py 41_Barburrito.py \
  42_Benugo.py 43_Boostjuice.py 44_Boswell.py 45_Brewhouse.py \
  46_Cineworld.py 47_Coffee1.py 48_CommonRooms.py 49_CookhousePub.py \
  --evidence-dir evidence/chains21_50
```

Successful outputs are written under
`chains21_50_collection/<chain>_<date>/`. Failed runs write diagnostics under
`evidence/chains21_50/<run-id>/<scraper>/`. The verified acceptance run
produced no failure bundles.

## Human decisions resolved (2026-08-19)

1. **Revolution:** the authoritative allergen app resolves but TCP connections
   time out locally, while current official menu pages return server errors.
   The food PDF alone is intentionally insufficient. **Decision: leave
   excluded.** No replacement endpoint or manual collection approved.
2. **Loch Fyne:** Greene King confirmed it ceased trading the restaurant brand
   in November 2023. **Decision: keep retired.** Do not substitute the
   separately owned Loch Fyne Oyster Bar.
3. **Asda Café:** public downloadable menu assets are from 2022 or earlier
   despite the current menu refresh and are intentionally rejected as stale.
   **Decision: leave excluded.** No in-store menu export/manual process
   approved.
4. **Crussh:** current menus exist on Deliveroo/Just Eat, but not on Crussh's
   official domain. **Decision: leave excluded.** Third-party delivery-platform
   data rejected as a substitute.

## Human decisions resolved (2026-08-19, continued)

5. **Boswell:** the current official page still links 2024 food/drink nutrition
   guides alongside a 2026 allergen guide. **Decision: keep the 2024 PDFs** —
   they are the official release, still linked live from the current page.

6. **Ben & Jerry's:** 5 of 43 rows (4 unique flavours — Churrifically
   Churros-y, Cherry Garcia, Double Caramel Brownie, Dulce De-lish) have empty
   `nutrition_image`, `nutrition_info`, `ingredients`, and `allergens` fields.
   This is not an OCR failure: the official benjerry.co.uk flavour pages for
   these SKUs publish no nutrition image at all. The other 38 rows are
   correctly populated via image URL + OCR. **Decision: accept the gap** — no
   alternate source investigation.
