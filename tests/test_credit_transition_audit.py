import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_credit_transition import reconcile


class CreditTransitionAuditTests(unittest.TestCase):
    def test_balanced_legacy_and_pending(self):
        accounts = [{"id": "a", "credit_balance": 95, "credit_reserved": 5}]
        ledger = [dict(account_id="a", available_delta=100, reserved_delta=0),
                  dict(account_id="a", available_delta=-5, reserved_delta=5)]
        requests = [dict(account_id="a", state="waiting", credit_cost=5)]
        report = reconcile(accounts, ledger, requests)
        self.assertEqual(report["ledgerMismatchAccounts"], 0)
        self.assertEqual(report["pendingReserveMismatchAccounts"], 0)
        self.assertEqual(report["pendingCredit"], 5)
        self.assertEqual(accounts[0]["credit_balance"], 95)
        self.assertEqual(report["sourceClassification"], "UNDETERMINED_ADMIN_REVIEW_REQUIRED")

    def test_missing_history_and_stranded_reserve(self):
        report = reconcile([dict(id="a", credit_balance=20, credit_reserved=3)], [], [])
        self.assertEqual(report["ledgerMismatchAccounts"], 1)
        self.assertEqual(report["pendingReserveMismatchAccounts"], 1)

    def test_terminal_requests_and_orphan_records(self):
        report = reconcile([], [dict(account_id="b", available_delta=0, reserved_delta=5)],
                           [dict(account_id="c", state="reserved", credit_cost=5),
                            dict(account_id="d", state="refunded", credit_cost=5)])
        self.assertEqual(report["orphanLedgerAccounts"], 1)
        self.assertEqual(report["orphanPendingAccounts"], 1)
        self.assertEqual(report["pendingRequests"], 1)


if __name__ == "__main__":
    unittest.main()
