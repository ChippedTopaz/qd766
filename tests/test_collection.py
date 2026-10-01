import json
import shutil
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766 import (
    PeriodSelection,
    build_collected_snapshot,
    build_fixture_snapshot,
    collect_snapshot,
    plan_evaluation_requests,
)
from qd766.collection import (
    BrowserTransport,
    CollectionError,
    RateLimitStop,
    SafetyStop,
    TransportFailure,
    TransportResponse,
)
from qd766.normalization import METRIC_GROUPS

ROOT_ID = "019d2be3-6a88-732b-8b17-b68020c8553a"
FORMALITY_ID = "019d2bfd-8e22-77ef-819f-e49460350904"


def response_for(group, *, status=201, root_id=ROOT_ID):
    if status not in (200, 201):
        return TransportResponse(status=status, body=b"{}", contentType="application/json")
    if group in METRIC_GROUPS:
        data = {
            "overview": {"departmentId": root_id, "departmentName": "Root"},
            "evaluation": [{"departmentId": "child-1", "departmentName": "Child"}],
        }
    else:
        data = {
            "parent": {"departmentId": root_id, "departmentName": "Root"},
            "children": [{"departmentId": "child-1", "departmentName": "Child"}],
        }
    body = json.dumps({"code": "OK", "data": data}, separators=(",", ":")).encode()
    return TransportResponse(status=status, body=body, contentType="application/json")


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post_json(self, url, payload):
        self.calls.append((url, payload))
        if not self.responses:
            raise AssertionError("Unexpected transport call")
        return self.responses.pop(0)


class FailingTransport:
    def __init__(self):
        self.calls = 0

    def post_json(self, url, payload):
        self.calls += 1
        raise TransportFailure("offline")


class FakeBrowserSocket:
    def __init__(self, value):
        self.value = value
        self.sent = []
        self.responses = []

    def send(self, raw):
        message = json.loads(raw)
        self.sent.append(message)
        self.responses.extend(
            [
                json.dumps({"method": "Network.requestWillBeSent"}),
                json.dumps(
                    {
                        "id": message["id"],
                        "result": {"result": {"value": self.value}},
                    }
                ),
            ]
        )

    def recv(self, timeout):
        return self.responses.pop(0)


class CollectionTest(unittest.TestCase):
    runtime = ROOT / "tests/runtime-collection"

    def setUp(self):
        shutil.rmtree(self.runtime, ignore_errors=True)
        self.runtime.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.runtime, ignore_errors=True)

    def test_request_plan_has_six_all_groups_and_five_formality_groups(self):
        period = PeriodSelection("quarter", 2026, 3)
        all_plan = plan_evaluation_requests(period, ROOT_ID)
        formality_plan = plan_evaluation_requests(period, ROOT_ID, FORMALITY_ID)
        self.assertEqual(len(all_plan), 6)
        self.assertEqual(len(formality_plan), 5)
        self.assertNotIn("handling-satisfaction", [item.group for item in formality_plan])
        self.assertEqual(
            next(item for item in all_plan if item.group == "handling-satisfaction").payload["fromDate"],
            "2026-07-01",
        )
        digitized = next(item for item in formality_plan if item.group == "dossier-digitized")
        self.assertEqual(digitized.payload["formalityID"], FORMALITY_ID)

    def test_browser_transport_posts_json_through_same_origin_page(self):
        expected = {
            "status": 201,
            "contentType": "application/json",
            "body": '{"code":"OK"}',
        }
        socket = FakeBrowserSocket(expected)
        transport = BrowserTransport(timeout_seconds=2)
        transport._socket = socket
        response = transport.post_json(
            "https://dichvucong.gov.vn/api/v1/reporting/evaluation/service-results",
            {"timeType": "year", "year": 2026},
        )
        self.assertEqual(response.status, 201)
        self.assertEqual(response.body, b'{"code":"OK"}')
        expression = socket.sent[0]["params"]["expression"]
        self.assertIn("fetch(url", expression)
        self.assertIn('"year": 2026', expression)

    def test_collection_is_sequential_checkpoints_raw_bytes_and_becomes_complete(self):
        period = PeriodSelection("year", 2026)
        plan = plan_evaluation_requests(period, ROOT_ID)
        responses = [response_for(item.group) for item in plan]
        expected_bodies = [response.body for response in responses]
        transport = FakeTransport(responses)
        sleeps = []
        output = self.runtime
        manifest = collect_snapshot(
            plan,
            period=period,
            output_dir=output,
            transport=transport,
            minimum_delay_seconds=1,
            jitter_seconds=0,
            sleeper=sleeps.append,
        )
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual([capture["group"] for capture in manifest["captures"]], [item.group for item in plan])
        self.assertEqual(len(transport.calls), 6)
        self.assertEqual(sleeps, [1] * 5)
        for item, body in zip(plan, expected_bodies, strict=True):
            self.assertEqual((output / item.outputFile).read_bytes(), body)
        saved = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, manifest)
        with self.assertRaisesRegex(CollectionError, "complete snapshot"):
            collect_snapshot(
                plan,
                period=period,
                output_dir=output,
                transport=FakeTransport([]),
                sleeper=lambda _: None,
            )

    def test_429_stops_immediately_and_resume_skips_verified_checkpoint(self):
        period = PeriodSelection("month", 2026, 9)
        plan = plan_evaluation_requests(period, ROOT_ID)
        first_transport = FakeTransport(
            [response_for(plan[0].group), response_for(plan[1].group, status=429)]
        )
        output = self.runtime
        with self.assertRaisesRegex(RateLimitStop, "429"):
            collect_snapshot(
                plan,
                period=period,
                output_dir=output,
                transport=first_transport,
                minimum_delay_seconds=0,
                jitter_seconds=0,
                sleeper=lambda _: None,
            )
        halted = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(halted["status"], "halted")
        self.assertEqual(len(halted["captures"]), 1)
        self.assertEqual(len(first_transport.calls), 2)

        remaining = FakeTransport([response_for(item.group) for item in plan[1:]])
        complete = collect_snapshot(
            plan,
            period=period,
            output_dir=output,
            transport=remaining,
            minimum_delay_seconds=0,
            jitter_seconds=0,
            sleeper=lambda _: None,
        )
        self.assertEqual(complete["status"], "complete")
        self.assertEqual(len(remaining.calls), 5)

    def test_wrong_root_fails_before_writing_raw_response(self):
        period = PeriodSelection("year", 2026)
        plan = plan_evaluation_requests(period, ROOT_ID)[:1]
        output = self.runtime
        with self.assertRaisesRegex(CollectionError, "Wrong root department"):
            collect_snapshot(
                plan,
                period=period,
                output_dir=output,
                transport=FakeTransport([response_for(plan[0].group, root_id="wrong")]),
                minimum_delay_seconds=0,
                jitter_seconds=0,
                sleeper=lambda _: None,
            )
        self.assertFalse((output / plan[0].outputFile).exists())
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "failed")

    def test_html_or_waf_response_halts_without_retry(self):
        period = PeriodSelection("year", 2026)
        plan = plan_evaluation_requests(period, ROOT_ID)[:1]
        transport = FakeTransport(
            [
                TransportResponse(
                    status=200,
                    body=b"<html><title>Request Rejected</title></html>",
                    contentType="text/html",
                )
            ]
        )
        with self.assertRaises(SafetyStop):
            collect_snapshot(
                plan,
                period=period,
                output_dir=self.runtime,
                transport=transport,
                minimum_delay_seconds=0,
                jitter_seconds=0,
                sleeper=lambda _: None,
            )
        self.assertEqual(len(transport.calls), 1)
        manifest = json.loads((self.runtime / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "halted")
        self.assertEqual(manifest["failure"]["reason"], "rejection-or-html-response")

    def test_transport_errors_have_a_bounded_retry_count(self):
        period = PeriodSelection("year", 2026)
        plan = plan_evaluation_requests(period, ROOT_ID)[:1]
        transport = FailingTransport()
        sleeps = []
        with self.assertRaisesRegex(CollectionError, "after retries"):
            collect_snapshot(
                plan,
                period=period,
                output_dir=self.runtime,
                transport=transport,
                minimum_delay_seconds=1,
                jitter_seconds=0,
                max_retries=2,
                sleeper=sleeps.append,
            )
        self.assertEqual(transport.calls, 3)
        self.assertEqual(sleeps, [1, 1])
        manifest = json.loads((self.runtime / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["failure"]["reason"], "transport-retry-limit")

    def test_collected_raw_responses_feed_the_same_normalized_statistics(self):
        period = PeriodSelection("year", 2026)
        plan = plan_evaluation_requests(period, ROOT_ID)
        transport = FakeTransport(
            [
                TransportResponse(
                    status=201,
                    body=(ROOT / "tests/fixtures" / item.group / "year-all.json").read_bytes(),
                    contentType="application/json",
                )
                for item in plan
            ]
        )
        collect_snapshot(
            plan,
            period=period,
            output_dir=self.runtime,
            transport=transport,
            minimum_delay_seconds=0,
            jitter_seconds=0,
            sleeper=lambda _: None,
        )
        collected = build_collected_snapshot(self.runtime)
        fixture = build_fixture_snapshot(ROOT / "tests/fixtures", period, "all")
        self.assertEqual(collected.status.state, "complete")
        self.assertEqual(collected.provinceAggregatedScore, fixture.provinceAggregatedScore)
        self.assertEqual(collected.provinceAggregatedMaximum, 100)
        self.assertEqual(
            [(dataset.group, len(dataset.children)) for dataset in collected.datasets],
            [(dataset.group, len(dataset.children)) for dataset in fixture.datasets],
        )
        self.assertEqual(
            [dataset.root.parameters for dataset in collected.datasets],
            [dataset.root.parameters for dataset in fixture.datasets],
        )


if __name__ == "__main__":
    unittest.main()
