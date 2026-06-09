from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import subprocess
import sys
import time


def run_scripts_parallel(script_files, max_workers=5, cwd=None, stop_on_error=False):
    """
    Run scraper scripts concurrently as separate Python processes.

    Args:
        script_files: list[str] like ["1_McDonalds.py", "2_Wetherspoons.py"]
        max_workers: max concurrent jobs
        cwd: working directory containing scripts (defaults to current dir)
        stop_on_error: if True, raise when any script fails

    Returns:
        dict keyed by script file with run metadata
    """
    collection = os.environ.get("MENUTRACKER_COLLECTION")
    if not collection:
        raise RuntimeError(
            "Collection folder not set. Run create_collection() before calling run_scripts_parallel()."
        )

    cwd = Path(cwd or Path.cwd())
    results = {}
    env = os.environ.copy()

    def _run_one(script_name):
        script_path = cwd / script_name
        if not script_path.exists():
            return {
                "script": script_name,
                "ok": False,
                "returncode": -999,
                "seconds": 0,
                "stdout": "",
                "stderr": f"File not found: {script_path}",
            }

        start = time.time()
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            env=env,
        )
        elapsed = round(time.time() - start, 2)
        return {
            "script": script_name,
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "seconds": elapsed,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    print(f"Starting {len(script_files)} scripts with max_workers={max_workers} in {cwd}")
    print(f"Collection: {collection}")
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_run_one, s): s for s in script_files}
        for fut in as_completed(futures):
            r = fut.result()
            results[r["script"]] = r
            status = "OK" if r["ok"] else "FAIL"
            print(f"[{status}] {r['script']} ({r['seconds']}s, rc={r['returncode']})")

    failed = [k for k, v in results.items() if not v["ok"]]
    print("\nSummary:")
    print(f"- Total: {len(results)}")
    print(f"- Success: {len(results) - len(failed)}")
    print(f"- Failed: {len(failed)}")

    if failed:
        print("\nFailed scripts (last stderr line):")
        for s in failed:
            lines = [ln for ln in results[s]["stderr"].splitlines() if ln.strip()]
            last = lines[-1] if lines else "(no stderr output)"
            print(f"- {s}: {last}")
        if stop_on_error:
            raise RuntimeError(f"Some scripts failed: {failed}")

    return results
