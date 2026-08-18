import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

from run_parallel import (
    classify_failure,
    make_issue_payload,
    run_scripts_parallel,
    sync_repair_issue,
    update_evidence_log,
    validate_outputs,
)


class RunnerTests(unittest.TestCase):
    def test_output_contract_requires_fresh_non_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "result.csv")
            output.write_text("old", encoding="utf-8")
            started_at = time.time()
            os.utime(output, (started_at - 1, started_at - 1))
            self.assertFalse(validate_outputs(directory, ["*.csv"], started_at)[0]["ok"])
            output.write_text("name\nnew\n", encoding="utf-8")
            os.utime(output, (started_at + 1, started_at + 1))
            self.assertTrue(validate_outputs(directory, ["*.csv"], started_at)[0]["ok"])

    def test_output_contract_rejects_empty_or_invalid_structured_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            started_at = time.time() - 1
            cases = {
                "header_only.csv": "name\n",
                "empty.json": "[]\n",
                "fake.pdf": "<html>blocked</html>",
            }
            for name, content in cases.items():
                output = root / name
                output.write_text(content, encoding="utf-8")
                result = validate_outputs(root, [name], started_at)[0]
                self.assertFalse(result["ok"])
                self.assertFalse(result["files"][0]["semantic_ok"])
                self.assertTrue(result["files"][0]["reason"])

    def test_output_contract_accepts_valid_structured_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            started_at = time.time() - 1
            (root / "result.csv").write_text("name\nitem\n", encoding="utf-8")
            (root / "result.json").write_text('[{"name": "item"}]\n', encoding="utf-8")
            (root / "result.pdf").write_bytes(b"%PDF-1.7\nfixture")
            for name in ("result.csv", "result.json", "result.pdf"):
                result = validate_outputs(root, [name], started_at)[0]
                self.assertTrue(result["ok"])
                self.assertTrue(result["files"][0]["semantic_ok"])

    def test_failure_classification(self):
        self.assertEqual(classify_failure({"stderr": "HTTP 429", "stdout": ""}), "external")
        self.assertEqual(
            classify_failure({"stderr": "NoSuchDriverException: Unable to obtain driver", "stdout": ""}),
            "external",
        )
        self.assertEqual(classify_failure({"stderr": "AssertionError", "stdout": ""}), "likely-code")

    def test_repeat_count_resets_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory, "evidence_log.json")
            update_evidence_log(log, "scraper.py", "likely-code", "run-1")
            repeated = update_evidence_log(log, "scraper.py", "likely-code", "run-2")
            self.assertEqual(repeated["consecutive_count"], 2)
            reset = update_evidence_log(log, "scraper.py", None, "run-3")
            self.assertEqual(reset["consecutive_count"], 0)

    def test_issue_payload_contains_no_process_logs(self):
        title, body = make_issue_payload(
            "scraper.py", "likely-code", ["run-1", "run-2"], [{"glob": "out/*.csv", "ok": False}]
        )
        self.assertIn("out/*.csv", body)
        self.assertNotIn("secret stderr", title + body)

    def test_existing_issue_is_commented_on(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            stdout = json.dumps([{"number": 7, "title": "repair me"}]) if args[2] == "list" else ""
            return SimpleNamespace(stdout=stdout)

        self.assertEqual(sync_repair_issue("repair me", "summary", run=fake_run), 7)
        self.assertEqual(calls[1][2], "comment")
        self.assertNotIn("create", calls[1])

    def test_parallel_runner_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            collection = root / "collection"
            collection.mkdir()
            (root / "fixture.py").write_text(
                "import os\nfrom pathlib import Path\n"
                "Path(os.environ['MENUTRACKER_COLLECTION'], 'result.txt').write_text('ok')\n",
                encoding="utf-8",
            )
            (root / "silent.py").write_text("print('no output file')\n", encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "scrapers": [
                            {"script": "fixture.py", "outputs": ["result.txt"]},
                            {"script": "silent.py", "outputs": ["missing.txt"]},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"MENUTRACKER_COLLECTION": str(collection)}):
                results = run_scripts_parallel(
                    ["fixture.py", "silent.py"], cwd=root, manifest_path=manifest,
                    evidence_dir=root / "evidence", max_workers=2
                )
            self.assertTrue(results["fixture.py"]["ok"])
            self.assertFalse(results["silent.py"]["ok"])
            bundle = Path(results["silent.py"]["evidence_bundle"])
            self.assertEqual(
                {"result.json", "output_validation.json", "stdout.txt", "stderr.txt"},
                {path.name for path in bundle.iterdir()},
            )


if __name__ == "__main__":
    unittest.main()
