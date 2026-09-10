import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
import zipfile

from collection_archive import build_run_summary, create_archive, parse_bucket_uri, upload_archive


class CollectionArchiveTests(unittest.TestCase):
    def test_parse_bucket_uri_requires_a_bucket_only_gcs_uri(self):
        self.assertEqual(
            "intake24-menutracker-collections",
            parse_bucket_uri("gs://intake24-menutracker-collections"),
        )
        with self.assertRaises(ValueError):
            parse_bucket_uri("gs://intake24-menutracker-collections/archives")
        with self.assertRaises(ValueError):
            parse_bucket_uri("https://intake24-menutracker-collections")

    def test_archive_contains_run_files_and_redacted_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            collection = root / "collection"
            evidence = root / "evidence"
            collection.mkdir()
            evidence.mkdir()
            (collection / "data.csv").write_text("item_name\nkebab\n", encoding="utf-8")
            (evidence / "result.json").write_text('{"ok": false}', encoding="utf-8")
            manifest = root / "scraper_manifest.json"
            manifest.write_text('{"scrapers": []}', encoding="utf-8")
            summary = build_run_summary(
                {
                    "fixture.py": {
                        "ok": False,
                        "returncode": 1,
                        "seconds": 0.1,
                        "run_id": "run-1",
                        "stdout": "secret stdout",
                        "stderr": "secret stderr",
                    }
                }
            )

            archive = create_archive(collection, evidence, manifest, summary, root / "wave.zip")

            with zipfile.ZipFile(archive) as zip_file:
                self.assertEqual(
                    {
                        "collection/data.csv",
                        "evidence/result.json",
                        "metadata/scraper_manifest.json",
                        "metadata/run-summary.json",
                    },
                    set(zip_file.namelist()),
                )
                metadata = json.loads(zip_file.read("metadata/run-summary.json"))
                self.assertEqual("fixture.py", metadata["results"][0]["script"])
                self.assertNotIn("stdout", metadata["results"][0])
                self.assertNotIn("stderr", metadata["results"][0])

    def test_upload_uses_create_only_precondition(self):
        archive = Path("wave.zip")
        client = Mock()

        uri = upload_archive(
            archive,
            "gs://intake24-menutracker-collections",
            "archives/run-1-collection.zip",
            client,
        )

        self.assertEqual(
            "gs://intake24-menutracker-collections/archives/run-1-collection.zip", uri
        )
        client.bucket.return_value.blob.return_value.upload_from_filename.assert_called_once_with(
            "wave.zip", if_generation_match=0
        )

    def test_upload_overwrite_drops_the_precondition(self):
        archive = Path("wave.zip")
        client = Mock()

        upload_archive(
            archive,
            "gs://intake24-menutracker-collections",
            "archives/run-1-collection.zip",
            client,
            overwrite=True,
        )

        client.bucket.return_value.blob.return_value.upload_from_filename.assert_called_once_with(
            "wave.zip"
        )


if __name__ == "__main__":
    unittest.main()
