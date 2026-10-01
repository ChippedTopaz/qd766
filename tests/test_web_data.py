import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WebDataTest(unittest.TestCase):
    def test_generated_dashboard_data_preserves_scope_and_score_policy(self):
        directory = ROOT / "tests/runtime-web-data"
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True)
        try:
            output = directory / "snapshots.json"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/build_web_data.py"),
                    "--output",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            data = json.loads(output.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(directory, ignore_errors=True)

        self.assertEqual(len(data["periods"]), 3)
        self.assertEqual(len(data["snapshots"]), 6)
        month = data["snapshots"]["month-2026-08:all"]
        selected = data["snapshots"]["month-2026-08:formality"]
        self.assertEqual(month["provinceAggregatedScore"], 59.92)
        self.assertEqual(month["provinceAggregatedMaximum"], 100)
        self.assertEqual(selected["provinceAggregatedScore"], 50.94)
        self.assertEqual(selected["provinceAggregatedMaximum"], 80)
        self.assertEqual(len(month["datasets"]), 6)
        self.assertEqual(len(selected["datasets"]), 5)
        self.assertNotIn(
            "handling-satisfaction",
            {dataset["group"] for dataset in selected["datasets"]},
        )
        online = next(
            dataset
            for dataset in month["datasets"]
            if dataset["group"] == "provide-online-tree"
        )
        self.assertEqual(online["scorePolicy"], "api-authoritative")
        self.assertTrue(online["root"]["parameters"])
        self.assertEqual(online["children"][0]["parameters"], {"scoreDelta": None})


if __name__ == "__main__":
    unittest.main()
