import unittest
from unittest.mock import patch

import Master_Compile


class MasterCompileTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
