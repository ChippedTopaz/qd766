"""Read-only regression tests for the current fixed session policy."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from qd766.backend.auth import SESSION_SECONDS, current_session, digest
from qd766.backend.models import LoginSession, UserAccount


class SessionLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 10, 15, 0, tzinfo=timezone.utc)
        self.expiry = self.start + timedelta(seconds=SESSION_SECONDS)
        self.session = SimpleNamespace(account_id="test-account", expires_at=self.expiry)
        self.account = SimpleNamespace(active=True)
        self.db = Mock()
        self.db.get.side_effect = lambda model, key: self.session if model is LoginSession else self.account

    def lookup(self, now, token="test-token"):
        with patch("qd766.backend.auth.datetime") as clock:
            clock.now.return_value = now
            return current_session(self.db, token)

    def test_activity_does_not_extend_fixed_eight_hour_expiry(self):
        self.assertEqual(SESSION_SECONDS, 8 * 3600)
        for hours in [1, 4, 7]:
            self.assertEqual(self.lookup(self.start + timedelta(hours=hours)), (self.session, self.account))
            self.assertEqual(self.session.expires_at, self.expiry)
        self.db.add.assert_not_called()
        self.db.commit.assert_not_called()

    def test_expiry_boundary_is_enforced(self):
        self.assertEqual(self.lookup(self.expiry - timedelta(seconds=1)), (self.session, self.account))
        self.assertEqual(self.lookup(self.expiry), (None, None))
        self.assertEqual(self.lookup(self.expiry + timedelta(seconds=1)), (None, None))

    def test_missing_revoked_or_disabled_session_rejected(self):
        self.assertEqual(self.lookup(self.start, None), (None, None))
        self.db.get.return_value = None
        self.db.get.side_effect = None
        self.assertEqual(self.lookup(self.start), (None, None))
        self.db.get.side_effect = lambda model, key: self.session if model is LoginSession else self.account
        self.account.active = False
        self.assertEqual(self.lookup(self.start), (None, None))

    def test_database_lookup_uses_hashed_cookie(self):
        self.lookup(self.start)
        self.assertEqual(self.db.get.call_args_list[0].args, (LoginSession, digest("test-token")))
        self.assertEqual(self.db.get.call_args_list[1].args, (UserAccount, "test-account"))


if __name__ == "__main__":
    unittest.main()
