import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.periods import PeriodSelection, build_evaluation_payload


class PeriodPayloadTest(unittest.TestCase):
    root_id = "019d2be3-6a88-732b-8b17-b68020c8553a"
    formality_id = "019d2bfd-8e22-77ef-819f-e49460350904"

    def test_satisfaction_maps_product_periods_to_inclusive_dates(self):
        cases = [
            (PeriodSelection("month", 2026, 9), "2026-09-01", "2026-09-30"),
            (PeriodSelection("quarter", 2026, 3), "2026-07-01", "2026-09-30"),
            (PeriodSelection("year", 2026), "2026-01-01", "2026-12-31"),
            (PeriodSelection("month", 2024, 2), "2024-02-01", "2024-02-29"),
        ]
        for period, start, end in cases:
            with self.subTest(period=period):
                payload = build_evaluation_payload(
                    "handling-satisfaction", period, self.root_id
                )
                self.assertEqual(payload["fromDate"], start)
                self.assertEqual(payload["toDate"], end)
                self.assertNotIn("timeType", payload)

    def test_satisfaction_rejects_formality(self):
        with self.assertRaisesRegex(ValueError, "does not support"):
            build_evaluation_payload(
                "handling-satisfaction",
                PeriodSelection("year", 2026),
                self.root_id,
                self.formality_id,
            )

    def test_formality_key_casing_matches_each_contract(self):
        regular = build_evaluation_payload(
            "transparency",
            PeriodSelection("quarter", 2026, 3),
            self.root_id,
            self.formality_id,
        )
        digitized = build_evaluation_payload(
            "dossier-digitized",
            PeriodSelection("quarter", 2026, 3),
            self.root_id,
            self.formality_id,
        )
        self.assertEqual(regular["formalityId"], self.formality_id)
        self.assertNotIn("formalityID", regular)
        self.assertEqual(digitized["formalityID"], self.formality_id)
        self.assertNotIn("formalityId", digitized)

    def test_generated_payloads_equal_all_33_captured_requests(self):
        manifest = json.loads(
            (ROOT / "tests/fixtures/manifest.m0.json").read_text(encoding="utf-8")
        )
        for capture in manifest["captures"]:
            if "/evaluation/" not in capture["url"]:
                continue
            group = capture["file"].split("/", 1)[0]
            period_type = capture["period"]
            value = {"month": 9, "quarter": 3, "year": None}[period_type]
            formality_id = (
                self.formality_id if capture["scope"] == "formality" else None
            )
            actual = build_evaluation_payload(
                group,
                PeriodSelection(period_type, 2026, value),
                self.root_id,
                formality_id,
            )
            self.assertEqual(actual, capture["payload"], capture["file"])


if __name__ == "__main__":
    unittest.main()
