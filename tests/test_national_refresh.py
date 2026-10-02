import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from qd766.backend.models import Base, NationalSummarySnapshot
from qd766.backend.national_summaries import store_national_summary, latest_national_summary
from qd766.national_summary import NationalSummaryCapture
from qd766.periods import PeriodSelection
from refresh_national_summaries import _missing_closed_periods, _current_periods


class NationalRefreshTests(unittest.TestCase):
    def test_same_content_is_fresh_observation_not_duplicate_version(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        now = datetime(2026,10,2,9,tzinfo=timezone.utc)
        def capture(at, digest="a"):
            return NationalSummaryCapture(PeriodSelection("year",2026), {},
                {"evaluation":[{} for _ in range(34)]}, digest*64, at)
        with Session(engine) as db:
            original, created = store_national_summary(db, capture(now))
            original_id = original.id
            first_stored = original.created_at
            same, created = store_national_summary(db, capture(now+timedelta(hours=3)))
            self.assertFalse(created)
            self.assertEqual(same.id, original_id)
            self.assertEqual(same.captured_at,now+timedelta(hours=3))
            self.assertEqual(same.created_at, first_stored)
            self.assertEqual(db.scalar(select(func.count()).select_from(NationalSummarySnapshot)),1)
            store_national_summary(db,capture(now+timedelta(hours=4),"b"))
            reverted, created = store_national_summary(db,capture(now+timedelta(hours=5)))
            self.assertFalse(created)
            self.assertEqual(latest_national_summary(db,PeriodSelection("year",2026)).id,original_id)
            store_national_summary(db,capture(now))
            self.assertEqual(reverted.captured_at,now+timedelta(hours=5))
        engine.dispose()

    def test_backfill_only_closed_missing_periods_and_hourly_checks_all_three(self):
        now=datetime(2026,10,2,22,tzinfo=timezone(timedelta(hours=7)))
        with patch("refresh_national_summaries.latest_national_summary",return_value=None):
            periods=_missing_closed_periods(None,2026,now)
        self.assertEqual(len(periods),12)
        self.assertEqual(periods[-1],PeriodSelection("quarter",2026,3))
        with patch("refresh_national_summaries.latest_national_summary",return_value=object()):
            self.assertEqual(_missing_closed_periods(None,2026,now),[])
        with self.assertRaises(ValueError):
            _missing_closed_periods(None,2027,now)
        self.assertEqual(_current_periods(now),[PeriodSelection("month",2026,10),
            PeriodSelection("quarter",2026,4),PeriodSelection("year",2026)])


if __name__ == "__main__":
    unittest.main()
