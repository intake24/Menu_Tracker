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
