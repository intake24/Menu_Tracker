# Chains 51–91 smoke test (19 August 2026)

Continuation of the manifest-driven collection wave after
[`CHAINS_21_50_SMOKE_TEST.md`](CHAINS_21_50_SMOKE_TEST.md). Covers every chain
ID from 51 to 91 that has a runnable scraper in the repository.

## Outcome

35 of 37 attempted chains pass through `Master_Compile.py` and
`scraper_manifest.json` after 9 repairs. 2 are retired, not scraped: **74
Town, Kitchen, and Pubs** (confirmed non-existent/closed — the Stonegate
brand and its tkmenus.com listing are both gone) and **87 AMT Coffee**
(exists, but publishes no digital nutrition/allergen source at all — a
different kind of block, see below). 2 chain IDs in this range were never
implemented and remain out of scope (listed below, not attempted).
`scraper_manifest.json` now has 84 entries (49 from chains 1–50 + 35 from
this pass).

## Scope

Numbered scripts exist for 30 of the chain IDs in this range originally; a
follow-up pass built 5 more (52, 59, 62, 66, 88 — see "New chains built"
below) after the user confirmed they are current, legitimate chains worth
scraping. The following 2 IDs still have no script and remain out of scope
(no work done — listed for visibility only):

| ID | Chain | Note |
| --- | --- | --- |
| 65 | Sainsbury's Cafe | Never implemented |
| 77 | Waterfields | Notebook already flags this as likely closed (20 Aug 2024); left retired |

## Parallel execution split

Non-Selenium (`requests`/`bs4`) scrapers ran together with `--workers 8`;
Selenium-driven scrapers ran separately with `--workers 3` to bound Chromium
memory use, per the existing Costa-concurrency caution in
`COLLECTION_WORKFLOW.md` and the notebook's own "2-3 workers for
Selenium-heavy scripts" note.

### Non-Selenium batch (15 scripts, `--workers 8`)

```bash
python Master_Compile.py <collection> \
  51_FarmhouseInns.py 54_HungryHorse.py 55_JoeJuice.py 57_GreeneKing.py 58_Vue.py \
  61_MorrisonsCafe.py 64_Pure.py 68_TankPaddle.py 69_TescoCafe.py 70_Cornish.py \
  71_ThomasBaker.py 72_TimHortons.py 84_Coco.py 86_HonestBurger.py \
  --workers 8
```

(`74_TownKitchenPubs.py` was in this run before being removed from the
manifest — see Blocked below.)

Result: 14/15 passed on the first run, total wall time ~46s. Row counts
(sanity-checked against the CSV, not just contract pass/fail):

| Chain | Records |
| --- | --- |
| 55 Joe & the Juice | 76 |
| 58 Vue | 8 (PDF manifest rows) |
| 61 Morrisons Cafe | 192 |
| 64 Pure | 306 |
| 68 Tank & Paddle | 54 |
| 69 Tesco Cafe | 57 |
| 70 The Cornish Bakery | 124 |
| 71 Thomas the Baker | 41 |
| 72 Tim Hortons | 278 |
| 84 Coco di Mama | 170 |
| 86 Honest Burger | 274 |
| 51 Farmhouse Inns / 54 Hungry Horse / 57 Greene King | 1 PDF each |

`86_HonestBurger.py` (requests-based) was used as the canonical script over
`86_HonestBurger_selenium.py`; both write the same output files, and the
non-Selenium version already passed cleanly, so the Selenium duplicate was
left unused rather than run.

### Selenium batch (15 scripts, `--workers 3`)

```bash
python Master_Compile.py <collection> \
  56_Leon.py 60_Marstons.py 63_Pieminister.py 67_StonehousePizza.py 75_VintageInns.py \
  78_BirdsBakery.py 79_Tortilla.py 80_tossed.py 81_BellaItalian.py 82_CafeRouge.py \
  83_TacoBell.py 85_RealGreek.py 89_Browns.py 90_ONeills.py 91_Nicholsons.py \
  --workers 3
```

Result: 7/15 passed on the first run at `--workers 3` (8 failures). Since
several failures were plain WebDriverWait/selector timeouts under 3
concurrent Chromium instances (only ~4.6GB free RAM in this environment),
the 8 failures were re-run serially (`--workers 1`) to separate real bugs
from concurrency-induced flakiness:

| Chain | `--workers 3` | Serial retry | Verdict |
| --- | --- | --- | --- |
| 81 Bella Italia | FAIL (`RemoteDisconnected`) | OK | Concurrency flake — no code change |
| 83 Taco Bell | FAIL (`RemoteDisconnected`) | OK | Concurrency flake — no code change |
| 67 Stonehouse Pizza | FAIL (timeout) | FAIL (same) | Real bug — fixed, see below |
| 75 Vintage Inns | FAIL (timeout) | FAIL (same) | Real bug — fixed, see below |
| 90 O'Neills | FAIL (timeout) | FAIL (same) | Real bug — fixed, see below |
| 91 Nicholson's | FAIL (no output) | FAIL (same) | Real bug — fixed, see below |
| 79 Tortilla | FAIL (0 records) | FAIL (same) | Real bug — fixed, see below |
| 80 Tossed | FAIL (timeout) | FAIL (same) | Real bug — fixed, see below |

Both `RemoteDisconnected` failures hit `menus.tenkites.com`/`nutritionix.com`
under concurrent load and passed cleanly alone — an operational conclusion,
not a code fix: **run these two, and Ten-Kites-platform scripts generally,
at low concurrency (1–3 workers) rather than mixed into a large parallel
batch.**

A content-quality pass (row counts and category diversity, not just
pass/fail) on the chains that already reported `OK` also caught one further
silent bug: **60 Marston's** returned only 2 rows against a page with 148
menu items and 9 sections — a real defect the manifest's non-empty-file
contract does not catch on its own.

## Repairs made

All fixes below were verified with a focused, single-worker
`Master_Compile.py` run against the exact affected script before being
counted as fixed.

- **76 Wasabi:** `76_Wasabi_obsolete.py` pinned a stale, hardcoded 2024 PDF
  URL that returned 404. Replaced with `76_Wasabi.py`, using
  `combo_PDFDownload` against the stable `https://www.wasabi.uk.com/menus/`
  page (same dynamic-discovery pattern as Boswell/Brewhouse), which
  correctly discovers the current (July 2026) nutritional guide PDF.
  `OK`, valid PDF signature.

- **67 Stonehouse Pizza, 75 Vintage Inns, 90 O'Neills, 91 Nicholson's**
  (shared Mitchells & Butlers template): each script discovered its menu
  page URLs with an xpath like `//*[@class='image parbase section']` or
  `//*[@class='button parbase section']`. The live sites now render menu
  tiles through a `<mab-menu-listing list="[JSON]">` web component instead
  — the old xpath either matched nothing or matched an unrelated promo
  block (e.g. a Christmas banner on O'Neills, which is why the run wasn't a
  clean 404: it "found" one wrong link and then found no food cards on it).
  Fixed by reading `aemPagePath` entries straight out of each
  `mab-menu-listing` element's `list` JSON attribute instead of the DOM
  anchor structure. All four verified `OK`:
  Stonehouse Pizza 233 rows, Vintage Inns 386 rows, O'Neills 361 rows,
  Nicholson's 326 rows. (`89_Browns.py`, the fifth script on this template,
  was already passing — its site still uses the older `MenuListing__grid`
  markup and was left untouched.)

- **79 Tortilla:** the site replaced its interactive per-item nutrition
  calculator (the ~350-line Selenium script's whole target) with a single
  downloadable PDF, and now says so directly on the page ("Please download
  our full nutrition PDF"). Rewrote `79_Tortilla.py` from a full Selenium
  scraper down to a 10-line `combo_PDFDownload` call — simpler and no
  longer needs a browser at all (moved out of the Selenium bucket entirely
  for future runs). Manifest contract updated to expect the PDF instead of
  JSON/CSV. `OK`, PDF downloaded.

- **80 Tossed:** the category-list selector (`ul.e1cxpgmd8`) was a
  CSS-in-JS build-hashed class name that rotates on every deploy of the
  ordering platform (tosseduk.vmos.io). Replaced with a stable selector
  based on the anchor `href` pattern (`a[href*='/menu/category/']`), which
  doesn't change between builds. `OK`, 121 rows.

- **60 Marston's:** the script waited only for the category headers
  (`<h2>`) to appear, then immediately queried for item elements — but
  items render progressively after the headers, so it was reading a
  partial snapshot (2 of 148 items, 1 of 9 sections). Added a short
  poll loop that waits for the item count to stop growing before reading
  it. `OK`, 834 rows (up from 2).

## New chains built (52, 59, 62, 66, 87, 88)

The user confirmed these 6 chain IDs are current, legitimate chains worth
scraping (previously listed as "never implemented"). Each source was
researched first (official page, PDF vs. HTML vs. image, request vs.
browser), then built following existing conventions and verified with a
real `Master_Compile.py` run.

- **52 Five Guys:** the UK nutrition & allergen guide PDF's filename embeds
  the most recently added product (currently a "Myprotein shake" update),
  so it can't be matched by a URL keyword. `52_FiveGuys.py` instead finds
  the link by its stable button text ("UK Nutrition & Allergen Guide"),
  same approach as `48_CommonRooms.py`'s successor-menu discovery. Plain
  `requests`, no Selenium needed. `OK`.

- **59 ODEON:** the food/drinks facts-and-figures page sits behind a
  queue-it waiting-room wall that blocks plain `requests` (redirects to
  `odeon.queue-it.net`). A real Selenium session gets past it; the PDFs
  themselves are served from Cloudflare and download fine via plain
  `requests` once their URLs are known, so `59_Odeon.py` uses Selenium only
  to read the page, then downloads the 3 `-uk-version.pdf` files
  (nutritional information, allergens matrix, pre-packed product matrix)
  with plain `requests` — skipping the Belfast/ROI variants and an
  unrelated Costa PDF also linked on the same page. `OK`.

- **62 Pho:** `combo_PDFDownload` with `keyword="Guide"` against
  `/nutrition/` (matches both "Allergen-Guide" and "Nutritional-Guidelines",
  skips an unrelated "Gender-Pay-Reporting" PDF on the same page). First run
  failed: the page links the same PDF twice, once as an absolute URL and
  once as a relative path, and `combo_PDFDownload` only resolves relative
  paths when given a `prex` base — added
  `prex="https://www.phocafe.co.uk"`. `OK` after the fix.

- **66 Soho Coffee:** two `combo_PDFDownload` calls against `/allergens/`
  (`keyword="Allergen-Matrix"`, `keyword="Nutritional-Matrix"`), deliberately
  narrow enough to skip an "Euphorium-Allergens-Pack" PDF for a different
  sub-brand on the same page. `OK`.

- **88 Chicken Cottage:** allergens are published as a single chart *image*
  (JPG), not a PDF or HTML table — no existing helper handles that.
  `88_ChickenCottage.py` discovers the current image URL from the stable
  `/allergens/` page, downloads it, and OCRs it into a JSON sidecar with the
  same graceful degradation as `39_BenJerry_selenium.py` (empty `ocr_text`
  if the optional `tesseract` binary isn't installed). `OK`; OCR text is
  legible but imperfect, consistent with the already-accepted Ben & Jerry's
  precedent for chart/image OCR.

- **87 AMT Coffee — blocked, not built:** researched via the menu page, the
  homepage, and the FAQ page; AMT's own menu page states outright "For
  allergen information, please visit your local AMT coffee shop" and no
  allergen/nutrition PDF, table, or image exists anywhere on
  amtcoffee.co.uk. No source to scrape — same class of block as 40 Asda
  Café. Not added to the manifest.

## Retired / blocked — no human decision pending

- **74 Town, Kitchen, and Pubs — confirmed non-existent, correct to skip.**
  The script's `tkmenus.com/mylocalpub/` target 404s, and the bare
  `tkmenus.com` domain now redirects to a generic corporate "Ten Kites" site
  with no brand directory — matching the notebook's own prior notes ("Cannot
  find the website", 16 Sep 2025 and 4 Nov 2025). A web search during this
  pass turned up a `stonegatepubs.com/locations/town-pub-and-kitchen/`
  listing that looked like a possible lead, but the user confirmed the chain
  itself is closed/non-existent — so that lead is moot, not merely
  unreachable. Retired the same way as 32 Loch Fyne and 77 Waterfields, not
  treated as a live network-access blocker. Removed from
  `scraper_manifest.json`.

- **87 AMT Coffee — confirmed no digital source, correct to skip.** No
  allergen/nutrition PDF, table, or image exists anywhere on
  amtcoffee.co.uk (menu page, homepage, FAQ all checked); the site says
  outright to ask in-store. Same class as 40 Asda Café. Not added to the
  manifest. User confirmed this finding.
