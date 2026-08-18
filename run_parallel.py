from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import subprocess
import sys
import time


DEFAULT_MANIFEST = Path(__file__).with_name("scraper_manifest.json")
EXTERNAL_FAILURE = re.compile(
    r"\b(?:403|429|5\d\d)\b|"
    r"dns|name or service not known|temporary failure in name resolution|"
    r"connection(?:error|refused|reset|aborted)|timed? ?out|timeout|"
    r"ssl|tls|certificate verify|"
    r"modulenotfounderror|no module named|nosuchdriverexception|"
    r"unable to obtain driver|driver executable|chromedriver|geckodriver|"
    r"selenium manager|browser driver",
    re.IGNORECASE,
)


def load_manifest(path=DEFAULT_MANIFEST):
    """Return manifest entries keyed by script name."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = data.get("scrapers") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ValueError("Manifest must contain a 'scrapers' list")

    manifest = {}
    for entry in entries:
        script = entry.get("script") if isinstance(entry, dict) else None
        outputs = entry.get("outputs") if isinstance(entry, dict) else None
        if not isinstance(script, str) or not script or not isinstance(outputs, list) or not outputs:
            raise ValueError("Each scraper needs a script and at least one output glob")
        if script in manifest or any(not isinstance(output, str) or not output for output in outputs):
            raise ValueError(f"Invalid or duplicate manifest entry: {script!r}")
        manifest[script] = outputs
    return manifest


def validate_outputs(collection, output_globs, started_at):
    """Validate that each glob has a fresh, non-empty file."""
    collection = Path(collection)
    contracts = []
    for pattern in output_globs:
        files = []
        for path in sorted(collection.glob(pattern)):
            if not path.is_file():
                continue
            stat = path.stat()
            files.append(
                {
                    "path": str(path.relative_to(collection)),
                    "size": stat.st_size,
                    "modified_at": stat.st_mtime,
                    "fresh": stat.st_mtime >= started_at,
                    "non_empty": stat.st_size > 0,
                }
            )
        contracts.append(
            {
                "glob": pattern,
                "ok": any(file["fresh"] and file["non_empty"] for file in files),
                "files": files,
            }
        )
    return contracts


def classify_failure(result):
    text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}"
    return "external" if EXTERNAL_FAILURE.search(text) else "likely-code"


def update_evidence_log(path, script, failure_class, run_id):
    """Record this completed run and return the scraper's new state."""
    path = Path(path)
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    previous = state.get(script, {})
    if failure_class is None:
        current = {"failure_class": None, "consecutive_count": 0, "run_ids": []}
    else:
        same = previous.get("failure_class") == failure_class
        current = {
            "failure_class": failure_class,
            "consecutive_count": previous.get("consecutive_count", 0) + 1 if same else 1,
            "run_ids": (previous.get("run_ids", []) if same else [])[-9:] + [run_id],
        }
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    state[script] = current
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return current


def make_issue_payload(script, failure_class, run_ids, output_validation):
    failed_globs = [item["glob"] for item in output_validation if not item["ok"]]
    output_lines = "\n".join(f"- `{pattern}`" for pattern in failed_globs) or "- None (process failure)"
    title = f"[scraper repair] {script}: {failure_class}"
    body = (
        "Automated repair candidate after consecutive completed runs.\n\n"
        f"- Script: `{script}`\n"
        f"- Failure class: `{failure_class}`\n"
        f"- Run IDs: {', '.join(f'`{run_id}`' for run_id in run_ids)}\n"
        "- Failed output contracts:\n"
        f"{output_lines}\n\n"
        "Raw stdout and stderr remain in the local evidence bundle."
    )
    return title, body


def sync_repair_issue(title, body, repository=None, run=subprocess.run):
    """Create one issue by exact title, or comment on the existing open issue."""
    repo_args = ["--repo", repository] if repository else []
    listed = run(
        ["gh", "issue", "list", *repo_args, "--state", "open", "--search", title,
         "--json", "number,title", "--limit", "100"],
        check=True,
        text=True,
        capture_output=True,
    )
    issue = next((item for item in json.loads(listed.stdout) if item["title"] == title), None)
    if issue:
        run(
            ["gh", "issue", "comment", str(issue["number"]), *repo_args, "--body", body],
            check=True,
            text=True,
            capture_output=True,
        )
        return issue["number"]
    created = run(
        ["gh", "issue", "create", *repo_args, "--title", title, "--body", body],
        check=True,
        text=True,
        capture_output=True,
    )
    return created.stdout.strip()


def _write_evidence(evidence_dir, run_id, result):
    bundle = Path(evidence_dir) / run_id / Path(result["script"]).stem
    bundle.mkdir(parents=True, exist_ok=True)
    metadata = {
        key: value for key, value in result.items()
        if key not in {"stdout", "stderr", "output_validation"}
    }
    (bundle / "result.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (bundle / "output_validation.json").write_text(
        json.dumps(result["output_validation"], indent=2) + "\n", encoding="utf-8"
    )
    (bundle / "stdout.txt").write_text(result["stdout"], encoding="utf-8")
    (bundle / "stderr.txt").write_text(result["stderr"], encoding="utf-8")
    return bundle


def run_scripts_parallel(
    script_files=None,
    max_workers=5,
    cwd=None,
    stop_on_error=False,
    manifest_path=DEFAULT_MANIFEST,
    evidence_dir=None,
    enable_github_issues=False,
    github_repository=None,
):
    """Run manifest-selected scrapers concurrently and validate their outputs."""
    collection = os.environ.get("MENUTRACKER_COLLECTION")
    if not collection:
        raise RuntimeError(
            "Collection folder not set. Run create_collection() before calling run_scripts_parallel()."
        )
    if enable_github_issues and (
        sys.platform != "darwin" or os.environ.get("COLAB_RELEASE_TAG") or Path("/content").exists()
    ):
        raise RuntimeError("GitHub issue creation is allowed only on the explicitly enabled trusted Mac")

    cwd = Path(cwd or Path.cwd())
    evidence_dir = Path(evidence_dir or cwd / "evidence")
    manifest = load_manifest(manifest_path)
    scripts = list(manifest) if script_files is None else list(script_files)
    unknown = [script for script in scripts if script not in manifest]
    if unknown:
        raise ValueError(f"Scripts are not in the manifest: {unknown}")
    if len(scripts) != len(set(scripts)):
        raise ValueError("A scraper can only be selected once per run")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    results = {}
    env = os.environ.copy()

    def run_one(script_name):
        script_path = cwd / script_name
        started_at = time.time()
        started_clock = time.monotonic()
        if not script_path.is_file():
            returncode, stdout, stderr = -999, "", f"File not found: {script_path}"
        else:
            try:
                process = subprocess.run(
                    [sys.executable, str(script_path)],
                    cwd=str(cwd),
                    text=True,
                    capture_output=True,
                    env=env,
                )
                returncode, stdout, stderr = process.returncode, process.stdout, process.stderr
            except OSError as error:
                returncode, stdout, stderr = -998, "", str(error)

        output_validation = validate_outputs(collection, manifest[script_name], started_at)
        return {
            "script": script_name,
            "ok": returncode == 0 and all(item["ok"] for item in output_validation),
            "returncode": returncode,
            "seconds": round(time.monotonic() - started_clock, 2),
            "started_at": datetime.fromtimestamp(started_at, timezone.utc).isoformat(),
            "stdout": stdout,
            "stderr": stderr,
            "output_validation": output_validation,
            "run_id": run_id,
        }

    print(f"Starting {len(scripts)} scripts with max_workers={max_workers} in {cwd}")
    print(f"Collection: {collection}")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_one, script): script for script in scripts}
        for future in as_completed(futures):
            result = future.result()
            results[result["script"]] = result
            if result["ok"]:
                update_evidence_log(evidence_dir / "evidence_log.json", result["script"], None, run_id)
            else:
                failure_class = classify_failure(result)
                result["failure_class"] = failure_class
                bundle = _write_evidence(evidence_dir, run_id, result)
                result["evidence_bundle"] = str(bundle)
                repeat = update_evidence_log(
                    evidence_dir / "evidence_log.json", result["script"], failure_class, run_id
                )
                if enable_github_issues and failure_class == "likely-code" and repeat["consecutive_count"] >= 2:
                    title, body = make_issue_payload(
                        result["script"], failure_class, repeat["run_ids"][-2:], result["output_validation"]
                    )
                    try:
                        result["repair_issue"] = sync_repair_issue(title, body, github_repository)
                    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
                        print(f"[WARN] Could not sync repair issue for {result['script']}: {error}")

            status = "OK" if result["ok"] else "FAIL"
            print(f"[{status}] {result['script']} ({result['seconds']}s, rc={result['returncode']})")

    failed = [script for script, result in results.items() if not result["ok"]]
    print(f"\nSummary:\n- Total: {len(results)}\n- Success: {len(results) - len(failed)}\n- Failed: {len(failed)}")
    if failed:
        print("\nFailed scripts (last stderr line):")
        for script in failed:
            lines = [line for line in results[script]["stderr"].splitlines() if line.strip()]
            print(f"- {script}: {lines[-1] if lines else '(no stderr output)'}")
        if stop_on_error:
            raise RuntimeError(f"Some scripts failed: {failed}")
    return results
