import sys
import unittest
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from queue_full_default_refresh import refresh_periods

class FullDefaultRefreshPlanTest(unittest.TestCase):
    def test_current_year_all_available_periods(self):
        periods=refresh_periods(2026,datetime(2026,10,5))
        self.assertEqual(len(periods),15)
        self.assertEqual((periods[0].type,periods[0].value),('month',9))
        self.assertEqual({p.value for p in periods if p.type=='month'},set(range(1,11)))
        self.assertEqual({p.value for p in periods if p.type=='quarter'},set(range(1,5)))
        self.assertEqual(len({(p.type,p.year,p.value) for p in periods}),15)
    def test_past_year(self):
        self.assertEqual(len(refresh_periods(2025,datetime(2026,10,5))),17)
    def test_january(self):
        self.assertEqual(len(refresh_periods(2026,datetime(2026,1,1))),3)
    def test_unavailable_year(self):
        for year in (1999,2027):
            with self.assertRaises(ValueError):
                refresh_periods(year,datetime(2026,10,5))
