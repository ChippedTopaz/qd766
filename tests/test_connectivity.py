import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.connectivity import probe_dvcqg_connectivity


def resolver(host, port, type):
    return [(None, None, None, None, ("14.238.3.76", port))]


class FakeResponse:
    def __init__(self, status=200, body=b"public home", content_type="text/html"):
        self.status = status
        self.body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size):
        return self.body[:size]


class ConnectivityTest(unittest.TestCase):
    def test_one_successful_get_is_reviewable_but_does_not_close_any_circuit(self):
        calls = []

        def open_once(request, timeout):
            calls.append((request.get_method(), request.full_url, timeout))
            return FakeResponse()

        result = probe_dvcqg_connectivity(resolver=resolver, open_once=open_once)
        self.assertTrue(result.safe_to_review_for_reenable)
        self.assertIsNone(result.stop_reason)
        self.assertEqual(calls, [("GET", "https://dichvucong.gov.vn/", 20.0)])

    def test_connection_reset_fails_closed_without_retry(self):
        calls = []

        def open_once(request, timeout):
            calls.append(request)
            raise ConnectionResetError(10054, "forcibly closed")

        result = probe_dvcqg_connectivity(resolver=resolver, open_once=open_once)
        self.assertFalse(result.safe_to_review_for_reenable)
        self.assertEqual(result.stop_reason, "https-connection-failure")
        self.assertEqual(result.error_type, "ConnectionResetError")
        self.assertEqual(len(calls), 1)

    def test_rejection_page_fails_closed(self):
        result = probe_dvcqg_connectivity(
            resolver=resolver,
            open_once=lambda request, timeout: FakeResponse(
                body=b"<html>Request Rejected</html>"
            ),
        )
        self.assertFalse(result.safe_to_review_for_reenable)
        self.assertEqual(result.stop_reason, "rejection-response")


if __name__ == "__main__":
    unittest.main()
