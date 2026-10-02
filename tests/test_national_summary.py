import json
import sys
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from qd766.collection import RateLimitStop, TransportResponse
from qd766.national_summary import (
    SERVICE_RESULTS_URL,
    build_national_summary_payload,
    collect_national_summary,
)
from qd766.periods import PeriodSelection
from refresh_national_summaries import _scheduled_period


def response_body():
    groups = {
        "CKMB": 7.96,
        "TDGQ": 17.68,
        "CLGQ": 8.56,
        "TTTT": 6.67,
        "MDHL": 11.37,
        "MDSH": 9.62,
    }
    evaluation = [
        {
            "departmentId": "019d2be3-6a88-732b-8b17-b68020c8553a",
            "departmentName": "UBND tỉnh Phú Thọ",
            "totalScore": 61.86,
            "groupScores": groups,
        }
    ]
    evaluation.extend(
        {
            "departmentId": str(uuid.UUID(int=index)),
            "departmentName": f"UBND tỉnh Kiểm thử {index}",
            "totalScore": 60.0,
            "groupScores": groups,
        }
        for index in range(1, 34)
    )
    return {
        "code": "OK",
        "data": {
            "overview": {"departmentName": "Cả nước", "totalScore": 61.51},
            "evaluation": evaluation,
        },
    }


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post_json(self, url, payload):
        self.calls.append((url, payload))
        return self.response


class NationalSummaryTest(unittest.TestCase):
    def test_scheduled_refresh_prioritizes_missing_year_then_rotates(self):
        at_one = datetime(2026, 10, 2, 1, 0)
        at_two = datetime(2026, 10, 2, 2, 0)
        at_three = datetime(2026, 10, 2, 3, 0)
        self.assertEqual(
            _scheduled_period(at_one, year_available=False),
            PeriodSelection("year", 2026),
        )
        self.assertEqual(
            _scheduled_period(at_one, year_available=True),
            PeriodSelection("month", 2026, 10),
        )
        self.assertEqual(
            _scheduled_period(at_two, year_available=True),
            PeriodSelection("year", 2026),
        )
        self.assertEqual(
            _scheduled_period(at_three, year_available=True),
            PeriodSelection("quarter", 2026, 4),
        )

    def test_period_payloads(self):
        self.assertEqual(
            build_national_summary_payload(PeriodSelection("month", 2026, 9)),
            {
                "timeType": "month",
                "year": 2026,
                "departmentType": "ADMINISTRATIVE_UNIT",
                "month": 9,
            },
        )
        self.assertEqual(
            build_national_summary_payload(PeriodSelection("quarter", 2026, 3)),
            {
                "timeType": "quarter",
                "year": 2026,
                "departmentType": "ADMINISTRATIVE_UNIT",
                "quarter": 3,
            },
        )
        self.assertEqual(
            build_national_summary_payload(PeriodSelection("year", 2026)),
            {
                "timeType": "year",
                "year": 2026,
                "departmentType": "ADMINISTRATIVE_UNIT",
            },
        )

    def test_collects_and_validates_summary(self):
        raw = json.dumps(response_body(), ensure_ascii=False).encode()
        transport = FakeTransport(
            TransportResponse(200, raw, "application/json; charset=utf-8")
        )
        capture = collect_national_summary(
            PeriodSelection("month", 2026, 9), transport
        )
        self.assertEqual(transport.calls[0][0], SERVICE_RESULTS_URL)
        self.assertEqual(capture.response_data["evaluation"][0]["totalScore"], 61.86)
        self.assertEqual(len(capture.raw_sha256), 64)

    def test_rate_limit_is_a_safety_stop(self):
        transport = FakeTransport(TransportResponse(429, b"rate limited", "text/plain"))
        with self.assertRaises(RateLimitStop):
            collect_national_summary(PeriodSelection("year", date.today().year), transport)


if __name__ == "__main__":
    unittest.main()
