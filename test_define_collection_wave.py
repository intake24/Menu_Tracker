import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from define_collection_wave import resolve_collection


class ResolveCollectionTests(unittest.TestCase):
    def test_explicit_name_returned_when_it_exists(self):
        with tempfile.TemporaryDirectory() as base:
            Path(base, "foo_collection").mkdir()
            with patch("define_collection_wave._detect_base_dir", return_value=base):
                self.assertEqual("foo_collection", resolve_collection("foo_collection"))

    def test_explicit_name_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as base:
            with patch("define_collection_wave._detect_base_dir", return_value=base):
                self.assertIsNone(resolve_collection("missing_collection"))

    def test_no_explicit_name_picks_most_recently_modified(self):
        with tempfile.TemporaryDirectory() as base:
            older = Path(base, "older_collection")
            newer = Path(base, "newer_collection")
            older.mkdir()
            newer.mkdir()
            now = time.time()
            os.utime(older, (now - 100, now - 100))
            os.utime(newer, (now, now))
            with patch("define_collection_wave._detect_base_dir", return_value=base):
                self.assertEqual("newer_collection", resolve_collection())

    def test_ignores_non_collection_dirs_and_files(self):
        with tempfile.TemporaryDirectory() as base:
            Path(base, "evidence_only").mkdir()
            Path(base, "some_file.txt").write_text("x", encoding="utf-8")
            with patch("define_collection_wave._detect_base_dir", return_value=base):
                self.assertIsNone(resolve_collection())

    def test_no_explicit_name_returns_none_when_base_dir_missing(self):
        with tempfile.TemporaryDirectory() as base:
            missing = os.path.join(base, "does_not_exist")
            with patch("define_collection_wave._detect_base_dir", return_value=missing):
                self.assertIsNone(resolve_collection())


if __name__ == "__main__":
    unittest.main()
