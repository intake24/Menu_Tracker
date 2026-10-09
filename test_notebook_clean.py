"""Fail if menutracker.ipynb carries run output, execution counts or editor leaks."""

import json
import unittest
from pathlib import Path

NOTEBOOK = Path(__file__).with_name("menutracker.ipynb")


class NotebookCleanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))

    def test_no_outputs_or_execution_counts(self):
        dirty = [
            i for i, c in enumerate(self.nb["cells"])
            if c["cell_type"] == "code" and (c.get("outputs") or c.get("execution_count") is not None)
        ]
        self.assertEqual(dirty, [], f"cells with stored output/execution count: {dirty}")

    def test_no_leaked_markup(self):
        leaked = [i for i, c in enumerate(self.nb["cells"]) if "<cell_type>" in "".join(c["source"])]
        self.assertEqual(leaked, [], f"cells containing literal <cell_type> markup: {leaked}")

    def test_no_local_kernel_name(self):
        name = self.nb["metadata"].get("kernelspec", {}).get("display_name", "")
        self.assertNotIn(".venv", name)


if __name__ == "__main__":
    unittest.main()
