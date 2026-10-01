import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ScoringEvidenceTest(unittest.TestCase):
    def test_checked_in_report_is_reproducible_and_verifies_online_formula(self):
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/analyze_scoring_formulas.py"),
                "--root",
                str(ROOT),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        generated = json.loads(completed.stdout)
        checked_in = json.loads(
            (ROOT / "docs/scoring-formula-analysis.m0.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(generated, checked_in)
        self.assertEqual(generated["result"], "PASS")
        online = next(
            formula
            for formula in generated["formulas"]
            if formula["group"] == "provide-online-tree"
        )
        self.assertEqual(online["status"], "verified-on-m0")
        self.assertEqual(online["profileId"], "qd766-online-v1")
        self.assertEqual(online["evidence"]["result"], "PASS")
        self.assertEqual(online["evidence"]["observations"], 6)


if __name__ == "__main__":
    unittest.main()
