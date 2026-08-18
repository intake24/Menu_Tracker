# Evidence bundle and repair-issue design

## Purpose

Make concurrent scraper runs observable without unattended code repair. A run
must detect process failures and stale, missing, or empty collection outputs.
It must save local diagnostic evidence and, on a trusted Mac only, surface
repeated likely-code failures as deduplicated GitHub Issues.

## Scope

- A shared `scraper_manifest.json` explicitly lists runnable scraper scripts
  and each script's required output globs.
- `run_parallel.py` runs manifest-selected scripts, captures stdout/stderr,
  and validates that every required output is non-empty and modified after the
  script started.
- Every failed run produces a local evidence bundle and updates a durable local
  evidence log.
- The runner classifies predictable external or local-environment failures as
  evidence-only. Other failures are likely-code failures.
- A likely-code failure repeated in two consecutive completed runs creates or
  updates one redacted GitHub repair issue when issue creation is explicitly
  enabled on the Mac.
- A repair-agent guide explains the manual repair workflow.
- Colab uses the same manifest and runner, but cannot create GitHub Issues.

## Non-goals

- No autonomous repair-agent invocation, automatic commits, or automatic PRs.
- No scheduler, server deployment, Google Drive integration, or stored
  Codex/GitHub credentials.
- No automatic scraper discovery, automatic retries, or raw log upload to
  GitHub.

## Manifest

`scraper_manifest.json` is the single source of truth for runnable scripts.
Each entry names one script and the output globs that must all be fresh and
non-empty for it to pass. The runner accepts an explicit subset so a notebook
can retain its current selective workflow.

## Evidence and repeat tracking

The repository-local ignored `evidence/` directory contains:

- one timestamped bundle per failed script, with result metadata, output
  validation, stdout, and stderr;
- a durable evidence log with the latest failure class and consecutive count
  per script.

An output failure is detected after the subprocess exits. A pre-existing file
does not satisfy an output contract unless its modification time is newer than
that script's start time.

## Classification and GitHub Issues

External/environmental failures include HTTP 403, 429, and 5xx responses,
DNS/connection/timeout/TLS errors, and missing local Python or browser-driver
dependencies. They write evidence but never create an issue.

All other process or output-contract failures are likely-code failures. After
the same scraper and failure class occur in two consecutive completed runs,
the runner may create or comment on a single open GitHub Issue. The issue body
contains only a redacted summary: script, failure class, run IDs, and failed
output contract. Complete logs remain local. Issues are never closed by the
runner; a repair PR closes them.

Issue creation is disabled by default and rejected in Colab. On the trusted
Mac, a maintainer explicitly enables it and provides their existing GitHub CLI
authentication.

## Repair-agent workflow

`docs/REPAIR_AGENT.md` instructs a manually started agent to read the issue
and local evidence bundle, reproduce minimally, make the smallest compatible
repair on a feature branch, verify the exact scraper and output contract, then
open a PR that closes the issue. It must preserve both notebook/Colab and
scheduled-run use.

## Verification

Small local tests will cover: output-contract freshness, external versus
likely-code classification, repeat counting, redacted issue payloads, and
deduplication. The existing runner's parallel subprocess behaviour remains
covered by an end-to-end fixture script.
