# MenuTracker

MenuTracker collects and preserves UK chain restaurant menu and nutritional data
for a named collection wave.

## Language

**Scraper failure**:
A scraper run that exits unsuccessfully or does not produce its required
non-empty CSV, JSON, or PDF output.
_Avoid_: successful run, transient log error

**Scraper manifest**:
The shared list of scraper scripts and their required collection outputs, used
by both manual Colab runs and scheduled runs.
_Avoid_: auto-discovery, notebook-only script list

**Repair candidate**:
A likely-code scraper failure repeated in two consecutive completed runs; it
creates or updates one GitHub Issue for that scraper and failure class.
_Avoid_: transient access failure, one-off run failure

**Evidence bundle**:
Local, run-specific diagnostic files containing raw process output and output
validation results. GitHub Issues contain only a redacted summary.
_Avoid_: issue attachment, public log dump

**Repair issue**:
One open GitHub Issue for a scraper and failure class. Repeated matching repair
candidates are appended to it; a repair pull request closes it.
_Avoid_: one issue per run, automatic closure

**Evidence log**:
The durable local record of scraper-run classifications and repeat counts used
to decide whether a repair issue is eligible.
_Avoid_: Colab state, GitHub as run history

**Manual repair**:
A maintainer starts a coding agent from a repair issue and its local evidence
bundle; the runner never invokes an autonomous repair agent.
_Avoid_: unattended code repair, automatic pull request

**Output contract**:
All outputs declared for a scraper in the scraper manifest must be non-empty
and modified during that run for it to succeed.
_Avoid_: existence-only check, partial output success
