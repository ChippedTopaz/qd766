import sys
import unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from qd766.backend.province_refresh import daily_refresh_candidates,due_daily_periods,refresh_cutoff,VIETNAM
from qd766.periods import PeriodSelection

class DailyPolicyTests(unittest.TestCase):
    def test_open_periods_refresh_each_local_day(self):
        now=datetime(2026,10,5,8,tzinfo=VIETNAM)
        candidates=daily_refresh_candidates(now)
        latest={(p.type,p.year,p.value):refresh_cutoff(p,now) for p in candidates}
        self.assertEqual(due_daily_periods(now,latest),[])
        for key in [('month',2026,10),('quarter',2026,4),('year',2026,None)]:
            latest[key]-=timedelta(seconds=1)
        self.assertEqual(len(due_daily_periods(now,latest)),3)

    def test_post_close_capture_required_but_not_every_day(self):
        now=datetime(2026,10,5,tzinfo=VIETNAM)
        latest={(p.type,p.year,p.value):refresh_cutoff(p,now) for p in daily_refresh_candidates(now)}
        latest[('month',2026,9)]=datetime(2026,9,28,tzinfo=VIETNAM)
        latest[('quarter',2026,3)]=datetime(2026,9,28,tzinfo=VIETNAM)
        self.assertEqual(set(due_daily_periods(now,latest)),{PeriodSelection('month',2026,9),PeriodSelection('quarter',2026,3)})
        latest[('month',2026,9)]=datetime(2026,10,1,tzinfo=VIETNAM)
        latest[('quarter',2026,3)]=datetime(2026,10,1,tzinfo=VIETNAM)
        self.assertFalse(any(p.type in ('month','quarter') and p.value in (9,3) for p in due_daily_periods(now+timedelta(days=2),latest)))

    def test_year_rollover_and_vietnam_midnight(self):
        now=datetime(2026,12,31,17,tzinfo=timezone.utc)
        candidates=daily_refresh_candidates(now)
        self.assertIn(PeriodSelection('year',2026),candidates)
        self.assertIn(PeriodSelection('year',2027),candidates)
        self.assertEqual(refresh_cutoff(PeriodSelection('year',2026),now),datetime(2027,1,1,tzinfo=VIETNAM))
        self.assertEqual(len(candidates),20)

    def test_naive_database_dates_are_utc(self):
        now=datetime(2026,10,5,8,tzinfo=VIETNAM)
        latest={(p.type,p.year,p.value):refresh_cutoff(p,now).astimezone(timezone.utc).replace(tzinfo=None)
                for p in daily_refresh_candidates(now)}
        self.assertEqual(due_daily_periods(now,latest),[])
