import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_data_coverage import previous, next_period_start, inventory
from qd766.backend.dashboard import GROUP_LABELS


class CoverageAuditTests(unittest.TestCase):
    def test_exact_previous_and_vietnam_period_boundary(self):
        self.assertEqual(previous(("month", 2026, 1)), ("month", 2025, 12))
        self.assertEqual(previous(("quarter", 2026, 1)), ("quarter", 2025, 4))
        self.assertEqual(previous(("year", 2026, None)), ("year", 2025, None))
        self.assertEqual(next_period_start(("quarter", 2026, 3)).isoformat(), "2026-10-01T00:00:00+07:00")
        self.assertEqual(next_period_start(("month", 2026, 12)).year, 2027)

    def test_missing_child_groups_and_unfinalized_closed_snapshot(self):
        dept = SimpleNamespace(name="Sở A", department_level="PROVINCE")
        datasets = []
        for index, group in enumerate(GROUP_LABELS):
            entities = [SimpleNamespace(id=index, entity_kind="root", api_score=0)]
            if index < 3:
                entities.append(SimpleNamespace(id=100+index, entity_kind="child", api_score=0,
                    department_id="agency", department=dept, parameters={}))
            datasets.append(SimpleNamespace(group_name=group, entities=entities))
        row = SimpleNamespace(period_type="month", year=2026, period_value=9,
            root_department_id="root", root_department=SimpleNamespace(name="Tỉnh A"),
            datasets=datasets, state="complete", created_at=datetime(2026,9,28,tzinfo=timezone.utc))
        db = SimpleNamespace(scalars=lambda query: None)
        with patch.object(db, "scalars", side_effect=[[],[row],[]]), patch(
            "audit_data_coverage.load_province_roots", return_value={
                "a": SimpleNamespace(root_department_id="root",province_name="Tỉnh A")}):
            report = inventory(db, datetime(2026,10,2,tzinfo=timezone.utc))
        period = next(p for p in report["periods"] if p["period"]=="month-2026-09")
        self.assertEqual(period["provinceDetailsSixGroups"], 1) # zeros are valid scores
        detail = period["details"][0]
        self.assertTrue(detail["closedButCapturedBeforeEnd"])
        self.assertEqual(detail["agencies"]["PROVINCE"]["withSixScores"],0)
        self.assertEqual(len(detail["incompleteAgencies"][0]["missingGroups"]),3)
        self.assertFalse(period["national"]["exists"])


if __name__ == "__main__":
    unittest.main()
