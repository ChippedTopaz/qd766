import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766 import PeriodSelection


class PeriodAvailabilityTest(unittest.TestCase):
    as_of = date(2026, 9, 27)

    def test_current_month_is_provisional_but_future_month_is_rejected(self):
        PeriodSelection("month", 2026, 8).validate_collectable(self.as_of)
        PeriodSelection("month", 2026, 9).validate_collectable(self.as_of)
        with self.assertRaisesRegex(ValueError, "future month"):
            PeriodSelection("month", 2026, 10).validate_collectable(self.as_of)

    def test_current_quarter_is_available_but_future_quarter_is_not(self):
        PeriodSelection("quarter", 2026, 3).validate_collectable(self.as_of)
        with self.assertRaisesRegex(ValueError, "Future quarter|future quarter"):
            PeriodSelection("quarter", 2026, 4).validate_collectable(self.as_of)

    def test_current_and_past_years_are_available(self):
        PeriodSelection("year", 2026).validate_collectable(self.as_of)
        PeriodSelection("month", 2025, 12).validate_collectable(self.as_of)
        with self.assertRaisesRegex(ValueError, "year is not available"):
            PeriodSelection("year", 2027).validate_collectable(self.as_of)


if __name__ == "__main__":
    unittest.main()
