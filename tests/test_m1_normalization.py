import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
sys.path.insert(0, str(ROOT / "src"))

from qd766 import PeriodSelection, build_fixture_snapshot, normalize_fixture
from qd766.normalization import IDENTITY_KEYS, SCORE_KEYS


class M1NormalizationTest(unittest.TestCase):
    def test_all_scope_is_complete_and_uses_only_api_scores(self):
        for period in (
            PeriodSelection("month", 2026, 8),
            PeriodSelection("quarter", 2026, 3),
            PeriodSelection("year", 2026),
        ):
            with self.subTest(period=period):
                snapshot = build_fixture_snapshot(FIXTURES, period, "all")
                self.assertEqual(snapshot.status.state, "complete")
                self.assertEqual(len(snapshot.datasets), 6)
                self.assertEqual(snapshot.provinceAggregatedMaximum, 100)
                self.assertEqual(
                    snapshot.provinceAggregatedScore,
                    round(sum(dataset.root.apiScore for dataset in snapshot.datasets), 2),
                )
                for dataset in snapshot.datasets:
                    self.assertEqual(dataset.scorePolicy, "api-authoritative")
                    for entity in [dataset.root, *dataset.children]:
                        self.assertEqual(entity.scoreSource, "dvcqg-api")
                        self.assertFalse(entity.formulaApplied)

    def test_formality_scope_marks_satisfaction_unsupported_not_missing(self):
        snapshot = build_fixture_snapshot(
            FIXTURES, PeriodSelection("year", 2026), "formality"
        )
        self.assertEqual(snapshot.status.state, "complete")
        self.assertEqual(len(snapshot.datasets), 5)
        self.assertEqual(snapshot.status.unsupportedGroups, ["handling-satisfaction"])
        self.assertEqual(snapshot.status.missingGroups, [])
        self.assertEqual(snapshot.formalityId, "019d2bfd-8e22-77ef-819f-e49460350904")

    def test_parameter_group_keeps_every_non_identity_non_score_field(self):
        path = FIXTURES / "formality-online-payment-tree/year-all.json"
        raw = json.loads(path.read_text(encoding="utf-8"))["data"]
        dataset = normalize_fixture(
            path,
            fixtures_root=FIXTURES,
            group="formality-online-payment-tree",
            period={"type": "year", "year": 2026},
            scope="all",
            formality_id=None,
        )
        expected = {
            "totalDossierOnlinePaymentSuccess",
            "totalDossierFinancialObligation",
            "totalDossierOnlineFormalityPaymentSuccess",
            "totalFeeDossierFormalityDistinct",
            "totalFeeDossierFormality",
            "totalFeeFormality",
        }
        self.assertTrue(expected <= dataset.root.parameters.keys())
        for key in expected:
            self.assertEqual(dataset.root.parameters[key], raw["parent"][key])
        self.assertEqual(dataset.formulaStatus, "parameters-retained-no-recalculation")

    def test_every_parameter_and_dataset_detail_remains_visible(self):
        for group in (
            "dvc-progress-tree",
            "provide-online-tree",
            "formality-online-payment-tree",
        ):
            with self.subTest(group=group):
                path = FIXTURES / group / "year-all.json"
                data = json.loads(path.read_text(encoding="utf-8"))["data"]
                dataset = normalize_fixture(
                    path,
                    fixtures_root=FIXTURES,
                    group=group,
                    period={"type": "year", "year": 2026},
                    scope="all",
                    formality_id=None,
                )
                raw_records = [data["parent"], *data["children"]]
                normalized_records = [dataset.root, *dataset.children]
                for raw, normalized in zip(raw_records, normalized_records, strict=True):
                    expected = {
                        key: value
                        for key, value in raw.items()
                        if key not in IDENTITY_KEYS | SCORE_KEYS | {"metrics"}
                    }
                    self.assertEqual(normalized.parameters, expected)
                self.assertEqual(
                    dataset.details,
                    {key: value for key, value in data.items() if key not in {"parent", "children"}},
                )

    def test_metric_nulls_and_quality_metadata_are_preserved(self):
        path = FIXTURES / "transparency/year-all.json"
        raw_bytes = path.read_bytes()
        original = json.loads(raw_bytes)
        before = copy.deepcopy(original)
        dataset = normalize_fixture(
            path,
            fixtures_root=FIXTURES,
            group="transparency",
            period={"type": "year", "year": 2026},
            scope="all",
            formality_id=None,
        )
        self.assertEqual(original, before)
        self.assertEqual(dataset.raw.sha256, hashlib.sha256(raw_bytes).hexdigest())
        normalized_metrics = {
            metric.code: metric for metric in dataset.root.metrics
        }
        raw_metrics = {metric["code"]: metric for metric in original["data"]["overview"]["metrics"]}
        for code, metric in normalized_metrics.items():
            self.assertEqual(metric.apiScore, raw_metrics[code]["score"])
            self.assertEqual(metric.extras, {
                key: value
                for key, value in raw_metrics[code].items()
                if key not in {"code", "name", "numerator", "denominator", "ratio", "score", "maxScore"}
            })

    def test_missing_files_produce_incomplete_snapshot_without_partial_total(self):
        snapshot = build_fixture_snapshot(
            ROOT / "tests/fixtures-does-not-exist",
            PeriodSelection("year", 2026),
            "all",
        )
        self.assertEqual(snapshot.status.state, "incomplete")
        self.assertEqual(len(snapshot.status.missingGroups), 6)
        self.assertIsNone(snapshot.provinceAggregatedScore)
        self.assertIsNone(snapshot.provinceAggregatedMaximum)

    def test_checked_in_m1_report_is_reproducible(self):
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/validate_m1.py"), "--root", str(ROOT)],
            check=True,
            capture_output=True,
            text=True,
        )
        generated = json.loads(completed.stdout)
        checked_in = json.loads(
            (ROOT / "docs/m1-validation-report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(generated, checked_in)
        self.assertEqual(generated["result"], "PASS")


if __name__ == "__main__":
    unittest.main()
