import unittest
from unittest.mock import patch

import Master_Compile


class MasterCompileTests(unittest.TestCase):
    def test_defaults_to_serial_execution(self):
        self.assertEqual(1, Master_Compile.parse_args(["Aug_collection_2026"]).workers)

    def test_archive_requires_an_explicit_evidence_directory(self):
        with self.assertRaises(SystemExit):
            Master_Compile.parse_args(
                ["Sep_collection_2026", "--archive-gcs", "gs://intake24-menutracker-collections"]
            )

    def test_collection_required_without_resume(self):
        with self.assertRaises(SystemExit):
            Master_Compile.parse_args([])

    @patch("Master_Compile.resolve_collection")
    def test_resume_with_explicit_collection_validates_it_exists(self, resolve_collection):
        resolve_collection.return_value = "Sep_collection_2026"
        args = Master_Compile.parse_args(["Sep_collection_2026", "--resume"])
        resolve_collection.assert_called_once_with("Sep_collection_2026")
        self.assertEqual("Sep_collection_2026", args.collection)

    @patch("Master_Compile.resolve_collection")
    def test_resume_errors_when_nothing_to_resume(self, resolve_collection):
        resolve_collection.return_value = None
        with self.assertRaises(SystemExit):
            Master_Compile.parse_args(["--resume"])

    @patch("Master_Compile.resolve_collection")
    def test_resume_errors_when_named_collection_not_found(self, resolve_collection):
        resolve_collection.return_value = None
        with self.assertRaises(SystemExit):
            Master_Compile.parse_args(["Missing_collection", "--resume"])

    @patch("Master_Compile.resolve_collection")
    def test_resume_auto_derives_evidence_dir(self, resolve_collection):
        resolve_collection.return_value = "2026-09-09_1851Z_weekly_collection"
        args = Master_Compile.parse_args(["--resume"])
        self.assertEqual("2026-09-09_1851Z_weekly_collection", args.collection)
        self.assertEqual(
            Master_Compile.ROOT / "collections" / "2026-09-09_1851Z_weekly_evidence",
            args.evidence_dir,
        )

    @patch("Master_Compile.resolve_collection")
    def test_resume_allows_archive_gcs_without_explicit_evidence_dir(self, resolve_collection):
        resolve_collection.return_value = "2026-09-09_1851Z_weekly_collection"
        args = Master_Compile.parse_args(
            ["--resume", "--archive-gcs", "gs://intake24-menutracker-collections"]
        )
        self.assertEqual(
            Master_Compile.ROOT / "collections" / "2026-09-09_1851Z_weekly_evidence",
            args.evidence_dir,
        )

    @patch("Master_Compile.resolve_collection")
    def test_resume_with_collection_and_scripts_restricts_correctly(self, resolve_collection):
        resolve_collection.return_value = "Sep_collection_2026"
        args = Master_Compile.parse_args(
            ["Sep_collection_2026", "--resume", "1_McDonalds.py", "9_Subway.py"]
        )
        self.assertEqual("Sep_collection_2026", args.collection)
        self.assertEqual(["1_McDonalds.py", "9_Subway.py"], args.scripts)

    @patch("Master_Compile.resolve_collection")
    @patch("Master_Compile.filter_for_resume")
    @patch("Master_Compile.load_manifest")
    @patch("Master_Compile.create_collection")
    @patch("Master_Compile.run_scripts_parallel")
    def test_main_resume_skips_when_everything_already_done(
        self, run, create_collection, load_manifest, filter_for_resume, resolve_collection
    ):
        resolve_collection.return_value = "Sep_collection_2026_collection"
        create_collection.return_value = "/tmp/Sep_collection_2026_collection"
        load_manifest.return_value = {"a.py": ["a_*.csv"], "b.py": ["b_*.csv"]}
        filter_for_resume.return_value = []

        with patch("builtins.print") as output:
            status = Master_Compile.main(["--resume", "Sep_collection_2026_collection"])

        run.assert_not_called()
        self.assertEqual(0, status)
        output.assert_called_once_with(
            "Collection 'Sep_collection_2026_collection' is already complete; nothing to resume."
        )

    @patch("Master_Compile.resolve_collection")
    @patch("Master_Compile.filter_for_resume")
    @patch("Master_Compile.load_manifest")
    @patch("Master_Compile.create_collection")
    @patch("Master_Compile.run_scripts_parallel")
    def test_main_resume_runs_only_remaining_scripts(
        self, run, create_collection, load_manifest, filter_for_resume, resolve_collection
    ):
        resolve_collection.return_value = "Sep_collection_2026_collection"
        create_collection.return_value = "/tmp/Sep_collection_2026_collection"
        load_manifest.return_value = {"a.py": ["a_*.csv"], "b.py": ["b_*.csv"]}
        filter_for_resume.return_value = ["b.py"]
        run.return_value = {"b.py": {"ok": True}}

        status = Master_Compile.main(["--resume", "Sep_collection_2026_collection"])

        self.assertEqual(["b.py"], run.call_args.args[0])
        self.assertEqual(0, status)

    @patch("Master_Compile.resolve_collection")
    @patch("Master_Compile.filter_for_resume")
    @patch("Master_Compile.load_manifest")
    @patch("Master_Compile.upload_archive")
    @patch("Master_Compile.create_archive")
    @patch("Master_Compile.create_collection")
    @patch("Master_Compile.run_scripts_parallel")
    def test_resume_archive_overwrites_a_previous_upload(
        self, run, create_collection, create_archive, upload_archive,
        load_manifest, filter_for_resume, resolve_collection,
    ):
        resolve_collection.return_value = "Sep_collection_2026_collection"
        create_collection.return_value = "/tmp/Sep_collection_2026_collection"
        load_manifest.return_value = {"b.py": ["b_*.csv"]}
        filter_for_resume.return_value = ["b.py"]
        run.return_value = {"b.py": {"ok": True, "run_id": "run-1"}}
        create_archive.return_value = "/tmp/wave.zip"
        upload_archive.return_value = "gs://intake24-menutracker-collections/archives/x.zip"

        status = Master_Compile.main(
            [
                "Sep_collection_2026_collection", "--resume",
                "--archive-gcs", "gs://intake24-menutracker-collections",
            ]
        )

        self.assertEqual(0, status)
        upload_archive.assert_called_once_with(
            "/tmp/wave.zip",
            "gs://intake24-menutracker-collections",
            "archives/Sep_collection_2026_collection.zip",
            overwrite=True,
        )

    @patch("Master_Compile.run_scripts_parallel")
    @patch("Master_Compile.create_collection")
    def test_main_configures_collection_and_returns_failure_status(self, create_collection, run):
        run.return_value = {
            "53_Harvester.py": {"ok": False, "evidence_bundle": "evidence/run/53_Harvester"}
        }

        with patch("builtins.print") as output:
            status = Master_Compile.main(
                ["Aug_collection_2026", "53_Harvester.py", "--workers", "2"]
            )

        create_collection.assert_called_once_with("Aug_collection_2026")
        self.assertEqual(["53_Harvester.py"], run.call_args.args[0])
        self.assertEqual(2, run.call_args.kwargs["max_workers"])
        self.assertEqual(Master_Compile.ROOT, run.call_args.kwargs["cwd"])
        output.assert_called_once_with("Evidence: evidence/run/53_Harvester")
        self.assertEqual(1, status)

    @patch("Master_Compile.upload_archive")
    @patch("Master_Compile.create_archive")
    @patch("Master_Compile.run_scripts_parallel")
    @patch("Master_Compile.create_collection")
    def test_archive_uploads_a_successful_run(
        self, create_collection, run, create_archive, upload_archive
    ):
        create_collection.return_value = "/tmp/Sep_collection_2026"
        run.return_value = {
            "fixture.py": {"ok": True, "run_id": "run-1", "returncode": 0, "seconds": 0.1}
        }
        create_archive.return_value = "/tmp/wave.zip"
        upload_archive.return_value = (
            "gs://intake24-menutracker-collections/archives/run-1-Sep_collection_2026.zip"
        )

        status = Master_Compile.main(
            [
                "Sep_collection_2026",
                "--evidence-dir",
                "evidence/run-1",
                "--archive-gcs",
                "gs://intake24-menutracker-collections",
            ]
        )

        self.assertEqual(0, status)
        upload_archive.assert_called_once_with(
            "/tmp/wave.zip",
            "gs://intake24-menutracker-collections",
            "archives/Sep_collection_2026.zip",
            overwrite=False,
        )

    @patch("Master_Compile.upload_archive")
    @patch("Master_Compile.create_archive")
    @patch("Master_Compile.run_scripts_parallel")
    @patch("Master_Compile.create_collection")
    def test_archive_runs_after_scraper_failure(
        self, create_collection, run, create_archive, upload_archive
    ):
        create_collection.return_value = "/tmp/Sep_collection_2026"
        run.return_value = {
            "broken.py": {"ok": False, "run_id": "run-1", "returncode": 1, "seconds": 0.1}
        }
        create_archive.return_value = "/tmp/wave.zip"
        upload_archive.return_value = "gs://intake24-menutracker-collections/archives/run-1.zip"

        status = Master_Compile.main(
            [
                "Sep_collection_2026",
                "--evidence-dir",
                "evidence/run-1",
                "--archive-gcs",
                "gs://intake24-menutracker-collections",
            ]
        )

        self.assertEqual(1, status)
        upload_archive.assert_called_once()

    @patch("Master_Compile.upload_archive")
    @patch("Master_Compile.create_archive")
    @patch("Master_Compile.run_scripts_parallel")
    @patch("Master_Compile.create_collection")
    def test_archive_failure_returns_status_two(
        self, create_collection, run, create_archive, upload_archive
    ):
        create_collection.return_value = "/tmp/Sep_collection_2026"
        run.return_value = {
            "fixture.py": {"ok": True, "run_id": "run-1", "returncode": 0, "seconds": 0.1}
        }
        create_archive.return_value = "/tmp/wave.zip"
        upload_archive.side_effect = OSError("bucket unavailable")

        status = Master_Compile.main(
            [
                "Sep_collection_2026",
                "--evidence-dir",
                "evidence/run-1",
                "--archive-gcs",
                "gs://intake24-menutracker-collections",
            ]
        )

        self.assertEqual(2, status)


if __name__ == "__main__":
    unittest.main()
