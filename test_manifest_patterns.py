import json
import tempfile
import unittest
from pathlib import Path


def subway_globs():
    manifest = json.loads((Path(__file__).parent / "scraper_manifest.json").read_text())
    return next(s["outputs"] for s in manifest["scrapers"] if s["script"] == "9_Subway.py")


class ManifestScriptTests(unittest.TestCase):
    def test_every_manifest_script_exists(self):
        root = Path(__file__).parent
        manifest = json.loads((root / "scraper_manifest.json").read_text())
        missing = [s["script"] for s in manifest["scrapers"]
                   if not (root / "food-chains" / s["script"]).exists()]
        self.assertEqual(missing, [])


class SubwayGlobTests(unittest.TestCase):
    def test_globs_match_the_filenames_subway_has_used(self):
        weeks = {
            "2026-10-26": ["C4_2026_Campaign_Allergen_Information_A4COMBINED.pdf",
                           "UKIBuildsandIngredientsNutritionalInformationSeptember2.pdf"],
            "2026-11-02": ["UKallergeninformationC5.pdf",
                           "UKIBuildsandIngredientsNutritionalInformationSeptember2.pdf"],
        }
        for week, names in weeks.items():
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp) / "9_Subway_x"
                folder.mkdir()
                for name in names:
                    (folder / name).write_bytes(b"%PDF")
                for pattern in subway_globs():
                    self.assertTrue(list(Path(tmp).glob(pattern)), f"{week}: {pattern}")


if __name__ == "__main__":
    unittest.main()
