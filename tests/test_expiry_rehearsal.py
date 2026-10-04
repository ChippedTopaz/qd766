import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from qd766.backend.app import create_app
from qd766.backend.auth import digest
from qd766.backend.config import Settings
from qd766.backend.local_credit_trial import identifier, mock_catalog
from qd766.backend.local_expiry_rehearsal import seed_expiry_rehearsal
from qd766.backend.models import Base, CreditWalletEvent, LoginSession, UserAccount


class ExpiryRehearsalTests(unittest.TestCase):
    def fixture(self, tier):
        app = create_app(Settings(database_url="sqlite+pysqlite://", public_read_only=True,
            require_login=True, google_client_id="test", google_client_secret="test-secret",
            google_redirect_uri="https://example.test/api/v1/auth/google/callback",
            paid_requests_enabled=True, formality_credit_cost=5, trial_credits_enabled=True))
        Base.metadata.create_all(app.state.engine)
        factory = app.state.session_factory
        factory.configure(info={"source_wallet_enabled": True})
        app.state.province_catalog_client = SimpleNamespace(load=lambda *a, **k: mock_catalog())
        now = datetime.now(timezone.utc)
        owner = {"subject": "google:fake-verified-owner", "email": "vietnt89@gmail.com"}
        with factory.begin() as db:
            self.assertTrue(seed_expiry_rehearsal(db, owner=owner, tier=tier, now=now))
            self.assertFalse(seed_expiry_rehearsal(db, owner=owner, tier=tier, now=now))
            account = db.scalar(select(UserAccount))
            db.add(LoginSession(token_hash=digest("test-session"), account_id=account.id,
                csrf_token="test-csrf", expires_at=now+timedelta(hours=1)))
        client = TestClient(app)
        client.cookies.set("qd766_session", "test-session")
        self.addCleanup(app.state.engine.dispose)
        return app, client, now

    def test_expired_library_then_redemption_and_new_request_for_both_tiers(self):
        for tier, cost in (("agency", 300), ("province", 600)):
            with self.subTest(tier=tier):
                app, client, now = self.fixture(tier)
                wallet = client.get("/api/v1/me/credits").json()
                self.assertEqual((wallet["subscriptionCredits"], wallet["purchasedCredits"]), (0, 600))
                self.assertTrue(wallet["canRedeem"])
                self.assertEqual(wallet["redemptionCost"], cost)
                library = client.get(f"/api/v1/me/formalities?period_type=year&year={now.year}").json()
                self.assertEqual(len(library["items"]), 1)
                detail = client.get(f"/api/v1/dashboard/selection?scope=formality&period_type=year&year={now.year}&formality_id={identifier('formality:1')}")
                self.assertEqual(detail.status_code, 200)
                headers = {"X-QD766-CSRF": "test-csrf"}
                selection = {"periodType": "year", "year": now.year,
                             "formalityIds": [str(identifier("formality:1"))]}
                own = client.post("/api/v1/me/collection-quote", json=selection, headers=headers)
                self.assertEqual(own.status_code, 200)
                self.assertEqual(own.json()["totalCredits"], 0)
                fresh = {**selection, "formalityIds": [str(identifier("formality:2"))]}
                blocked = client.post("/api/v1/me/collection-quote", json=fresh, headers=headers)
                self.assertEqual(blocked.status_code, 403)
                self.assertEqual(blocked.json()["blockedReason"], "subscription_expired")
                self.assertEqual(blocked.json()["quote"], "")
                self.assertEqual(blocked.json()["items"][0]["id"], str(identifier("formality:2")))
                self.assertEqual(blocked.json()["totalCredits"], 5)
                self.assertEqual(client.get("/api/v1/me/credits").json()["reservedCredits"], 0)
                token = str(uuid.uuid4())
                renewal = {"token": token, "expectedCost": cost}
                url = "/api/v1/me/subscription/redemption"
                self.assertEqual(client.post(url, json=renewal).status_code, 403)
                self.assertEqual(client.post(url, json={**renewal, "expectedCost": 900-cost}, headers=headers).status_code, 409)
                self.assertEqual(client.post(url, json=renewal, headers=headers).status_code, 200)
                self.assertEqual(client.post(url, json=renewal, headers=headers).status_code, 200)
                wallet = client.get("/api/v1/me/credits").json()
                self.assertEqual(wallet["purchasedCredits"], 600-cost)
                self.assertEqual(wallet["subscriptionCredits"], 0)
                self.assertFalse(wallet["canRedeem"])
                self.assertIsNotNone(wallet["subscriptionEndsAt"])
                if tier == "agency":
                    quote = client.post("/api/v1/me/collection-quote", json=fresh, headers=headers)
                    self.assertEqual(quote.status_code, 200)
                    self.assertEqual(quote.json()["totalCredits"], 5)
                    result = client.post("/api/v1/me/formality-requests", headers=headers,
                        json={"quote": quote.json()["quote"], "token": str(uuid.uuid4())})
                    self.assertEqual(result.status_code, 202)
                    self.assertEqual(result.json()["availableCredits"], 295)
                with app.state.session_factory() as db:
                    self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent)
                        .where(CreditWalletEvent.event_key.startswith("redeem:"))), 1)

    def test_builder_rejects_non_owner_or_disabled_wallet(self):
        app, client, now = self.fixture("agency")
        with app.state.session_factory.begin() as db:
            with self.assertRaises(ValueError):
                seed_expiry_rehearsal(db, owner={"subject": "google:other", "email": "other@example.test"}, tier="agency", now=now)
            db.info["source_wallet_enabled"] = False
            with self.assertRaises(ValueError):
                seed_expiry_rehearsal(db, owner={"subject": "google:fake-verified-owner", "email": "vietnt89@gmail.com"}, tier="agency", now=now)


if __name__ == "__main__":
    unittest.main()
