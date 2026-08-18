# MenuTracker collection workflow

This guide covers the manifest-based collection command, its data and evidence
files, and the manual repair workflow. Run all commands from the repository
root unless a command says otherwise.

The latest verified first-20 acceptance result and row-count audit are in
[`FIRST_20_SMOKE_TEST.md`](FIRST_20_SMOKE_TEST.md).

## Process flow

```text
Master_Compile.py
  -> creates the collection folder and exports MENUTRACKER_COLLECTION
  -> reads scraper_manifest.json
  -> runs all or selected scraper scripts (serially by default)
  -> each scraper writes into a dated chain subdirectory
  -> validates every declared output as fresh, non-empty, and parseable
     -> pass: prints OK and resets that scraper's failure count
     -> fail: writes a local evidence bundle and classifies the failure
        -> external: evidence only
        -> likely-code twice consecutively: optionally opens/updates one issue
  -> exits 0 when every scraper passes, otherwise exits 1
```

`scraper_manifest.json` is the source of truth. Running the command without
script names runs every declared entry, not every historical scraper in the
repository.

## 1. Prepare the environment

Create and activate the project's virtual environment, then install the
requirements:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Selenium scrapers also require Chrome or Chromium; `helpers.py` detects the
installed browser and obtains a compatible driver.

Check the available command options:

```bash
python Master_Compile.py --help
```

### Workflow files

| Path | Role |
| --- | --- |
| `Master_Compile.py` | Command-line entry point. Creates the collection, selects scripts, invokes the runner, prints evidence paths, and returns a shell status. |
| `scraper_manifest.json` | Sole registry of runnable scripts and required output globs. |
| `run_parallel.py` | Runs subprocesses, captures logs, validates outputs, classifies failures, writes evidence, and optionally synchronizes repair issues. |
| `define_collection_wave.py` | Creates the wave folder and sets `MENUTRACKER_COLLECTION`. |
| `helpers.py` | Shared folder, browser, download, and scraper helpers. |
| `<number>_<chain>.py` | Direct runnable scraper selected by a manifest entry. |
| `Scrapy_spiders/` | Scrapy project and site-specific spider implementations used by scraper scripts. |
| `docs/REPAIR_AGENT.md` | Constraints for a manually initiated repair and pull request. |

## 2. Define output contracts

Every runnable scraper needs one entry in `scraper_manifest.json`:

```json
{
  "script": "53_Harvester.py",
  "outputs": [
    "53_Harvester_*/harvester_nutrition.json",
    "53_Harvester_*/harvester_nutrition.csv"
  ]
}
```

- `script` is a Python file relative to the repository root.
- Each `outputs` value is a glob relative to the collection folder.
- Every declared glob must match at least one regular file that is non-empty
  and modified after that scraper process started.
- CSV outputs need a header and a nonblank data row, JSON outputs must parse
  and be nonempty, and PDF outputs must begin with a PDF signature.
- A scraper that exits successfully but misses one output contract still
  fails. Old output files never make a new run pass.

Add a scraper only after its filenames are stable enough to express these
contracts. Do not add automatic discovery: an explicit manifest prevents old
or experimental scripts from running accidentally.

## 3. Run a collection

Run every manifest entry serially. This is the safe default for a mixed wave
containing Selenium scrapers:

```bash
python Master_Compile.py Aug_collection_2026
```

Increase `--workers` only for a known-safe subset. In particular, Costa must
run without another active browser scraper; concurrent baseline runs killed
its browser session while the same full scrape passed with one worker.

Run a selected subset by giving exact manifest script names:

```bash
python Master_Compile.py Aug_collection_2026 \
  22_TobyCarvery.py 73_TopGolf.py
```

Select one scraper while debugging to keep logs and browser activity simple:

```bash
python Master_Compile.py Aug_collection_2026 53_Harvester.py --workers 1
```

The collection argument may also be an absolute path. A relative name is
created under the current directory locally, or under the MenuTracker Google
Drive directory when the existing Colab path is detected.

Do not run `define_collection_wave.py` first. `Master_Compile.py` calls
`create_collection()` and passes the resulting `MENUTRACKER_COLLECTION`
environment variable to every scraper subprocess.

### Optional repair issues

Issue creation is off by default. It is available only on the explicitly
trusted Mac, requires an authenticated GitHub CLI, and applies only after the
same likely-code failure occurs in two consecutive completed runs:

```bash
python Master_Compile.py Aug_collection_2026 53_Harvester.py \
  --workers 1 \
  --github-issues \
  --github-repository intake24/Menu_Tracker
```

Colab and other operating systems reject `--github-issues`. External failures
never create repair issues. Raw logs remain local and are not copied to
GitHub.

## 4. Read the outcomes

The terminal prints one line per completed scraper and a final summary:

```text
[OK] 73_TopGolf.py (2.1s, rc=0)
[FAIL] 53_Harvester.py (8.3s, rc=1)
```

- `OK` means the process returned zero and every output contract passed.
- `FAIL` means the process failed or at least one output was missing, empty,
  or stale.
- `rc` is the subprocess return code.
- The command exits `0` only when every selected scraper passes; otherwise it
  exits `1`, so shell scripts and schedulers can detect the failed wave.

### Successful data layout

Scraped data belongs under the collection folder, not under `evidence/`:

```text
Aug_collection_2026/
├── 22_TobyCarvery_Aug-18-2026/
│   ├── tobycarvery_nutrition.csv
│   └── tobycarvery_nutrition.json
├── 53_Harvester_Aug-18-2026/
│   ├── harvester_nutrition.csv
│   └── harvester_nutrition.json
└── 73_TopGolf_Aug-18-2026/
    ├── legacy_menu.pdf
    ├── topgolf_items.csv
    └── topgolf_items.json
```

The chain subdirectory name is `<chain>_<Mon-DD-YYYY>`. CSV files are the
tabular collection results. JSON files retain the scraper's structured result.
Some chains also retain source PDFs or other intermediate artifacts. Exact
required filenames come from the manifest; additional files are not validated.

Collection folders and generated CSV, JSON, PDF, and evidence files are local
run artifacts and should not be committed.

`Master_Compile.py` stops at validated chain-level outputs. It does not merge
or standardise the collected chains; that remains a separate downstream phase.

### Failed-run evidence layout

Only failed scrapers receive a timestamped evidence bundle:

```text
evidence/
├── evidence_log.json
└── 20260818T164506.391763Z/
    └── 53_Harvester/
        ├── result.json
        ├── output_validation.json
        ├── stdout.txt
        └── stderr.txt
```

| File | Definition |
| --- | --- |
| `result.json` | Script, pass/fail state, return code, elapsed seconds, UTC start time, run ID, and failure class. Large process logs are excluded. |
| `output_validation.json` | One record per manifest glob, including every matched path, byte size, modification time, freshness, non-empty state, semantic result, and reason. |
| `stdout.txt` | Complete captured standard output from the scraper subprocess. |
| `stderr.txt` | Complete captured standard error and traceback from the scraper subprocess. |
| `evidence_log.json` | Latest failure class, consecutive count, recent run IDs, and update time for each scraper. A successful run resets its count. |

The run ID is a UTC timestamp. Evidence contains diagnostics, not result CSVs;
follow paths in `output_validation.json` back to the collection folder.

## 5. Troubleshoot a failure

Work in this order:

1. Copy the `Evidence: evidence/<run-id>/<scraper>` path printed after the
   terminal summary.
2. Open `result.json`. A non-zero `returncode` means the scraper process
   failed; return code zero with `ok: false` points to output validation.
3. Open `output_validation.json`. For each failed glob, check whether files
   are absent, empty, marked `fresh: false`, or have `semantic_ok: false`, then
   read the accompanying `reason`.
4. Read the last useful lines of `stderr.txt`, then consult `stdout.txt` for
   the scraper's progress immediately before the failure.
5. Reproduce only that scraper with one worker and a new collection folder:

   ```bash
   python Master_Compile.py repair_collection_20260818 \
     53_Harvester.py --workers 1
   ```

6. Determine whether the cause is external or in code. HTTP 403/429/5xx,
   DNS, connection, timeout, TLS, missing dependency, and browser-driver errors
   are classified as `external`. Selector, parsing, exception, and output
   contract defects are normally `likely-code`.
7. Repair the shared/root cause with the smallest compatible change. Preserve
   both local and Colab operation.
8. Run the focused tests, then repeat the exact one-scraper command. The repair
   is verified only when the terminal reports `OK` and every manifest contract
   passes.

Common symptoms:

| Symptom | Check |
| --- | --- |
| `Scripts are not in the manifest` | Use the exact `script` value from `scraper_manifest.json`, or add a reviewed contract for the scraper. |
| Return code `0` but status `FAIL` | Inspect failed globs; the scraper likely wrote a different filename/location, no fresh file, or an empty/malformed CSV, JSON, or PDF. |
| Browser/driver failure | Confirm Chrome or Chromium is installed, then inspect `stderr.txt`; these are normally external failures. |
| No CSV inside `evidence/` | Expected. Result data is under the collection folder; evidence contains only failure diagnostics. |
| No evidence directory for an `OK` scraper | Expected. Successful runs update only `evidence_log.json`. |
| No GitHub issue | Confirm Mac execution, explicit flags, GitHub CLI authentication, a likely-code classification, and two consecutive failures. |

## 6. Use an agent for repair

Agent assistance is manual: a failed run does not modify code, commit, or open
a pull request by itself. Give the agent the local bundle path and exact
scraper, and tell it to follow `AGENTS.md` and `docs/REPAIR_AGENT.md`.

Example request:

```text
Diagnose 53_Harvester.py using
evidence/<run-id>/53_Harvester/. Follow AGENTS.md and
docs/REPAIR_AGENT.md. Work on the active feature bookmark, do not move main,
do not upload raw logs or collected data, fix the root cause, run the focused
tests, and verify the exact scraper through Master_Compile.py with one worker.
Do not commit until I review the diff.
```

Before accepting an agent repair:

1. Confirm `jj status` shows the intended feature work and no unrelated files.
2. Review `jj diff`; collected data and `evidence/` must remain untracked.
3. Require the focused unit tests and the exact manifest scraper smoke test.
4. Check the new collection's CSV/JSON directly and compare row counts and
   required columns with the previous successful wave.
5. Commit with the repository's Conventional Commit format and keep `main`
   unchanged until the feature is reviewed and merged.

For a repair issue and pull-request workflow, continue with
[`REPAIR_AGENT.md`](REPAIR_AGENT.md).
