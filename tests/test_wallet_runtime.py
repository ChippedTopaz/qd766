import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from qd766.backend.config import Settings
from qd766.backend.app import create_app
from qd766.backend.models import Base
from qd766.backend.public_deployment import public_settings, CALLBACK
from qd766.backend.wallet_runtime import validate_wallet_runtime, verify_real_wallet_schema


def real_settings():
    return Settings(real_wallet_enabled=True, public_read_only=True, require_login=True,
        invite_required=True, paid_requests_enabled=True, trial_credits_enabled=True,
        trial_credit_management=True, formality_credit_cost=5,
        google_client_id="test.apps.googleusercontent.com", google_client_secret="fake",
        google_redirect_uri=CALLBACK, database_url="postgresql+psycopg://user@127.0.0.1/qd766_restore_test")


class WalletRuntimeTests(unittest.TestCase):
    def test_opt_in_config_and_default_disabled(self):
        validate_wallet_runtime(real_settings())
        self.assertTrue(real_settings().source_wallet_enabled)
        with patch.dict(os.environ, {"QD766_REAL_WALLET_ENABLED": "true", "QD766_SOURCE_WALLET_TRIAL": "true"}):
            self.assertFalse(Settings.from_env().source_wallet_enabled)
        public = public_settings({"QD766_DATABASE_PASSWORD": "fake", "QD766_REAL_WALLET_ENABLED": "true"},
            {"QD766_GOOGLE_CLIENT_ID": "test.apps.googleusercontent.com",
             "QD766_GOOGLE_CLIENT_SECRET": "fake", "QD766_GOOGLE_REDIRECT_URI": CALLBACK})
        self.assertFalse(public.source_wallet_enabled)
        self.assertFalse(public.paid_requests_enabled)

    def test_fail_closed_before_engine_creation(self):
        cases = [dict(local_google_trial=True), dict(source_wallet_trial=True),
            dict(public_read_only=False), dict(require_login=False), dict(invite_required=False),
            dict(paid_requests_enabled=False), dict(trial_credits_enabled=False),
            dict(trial_credit_management=False), dict(formality_credit_cost=3), dict(sql_echo=True),
            dict(google_redirect_uri="http://127.0.0.1:8771/api/v1/auth/google/callback"),
            dict(database_url="sqlite+pysqlite://"),
            dict(database_url="postgresql+psycopg://user@remote/qd766"),
            dict(database_url="postgresql+psycopg://user@localhost/qd766_credit_test"),
            dict(database_url="postgresql+psycopg://user@localhost/qd766?options=-csearch_path=test")]
        for changes in cases:
            with self.subTest(changes=changes), patch("qd766.backend.app.create_database_engine") as engine:
                with self.assertRaises(ValueError):
                    create_app(replace(real_settings(), **changes))
                engine.assert_not_called()

    def test_real_session_policy_distinct_from_local_simulation(self):
        from sqlalchemy import create_engine
        engine = create_engine("sqlite+pysqlite://")
        try:
            # Dependency substitution only; the configured runtime remains PostgreSQL.
            with patch("qd766.backend.app.create_database_engine", return_value=engine):
                app = create_app(real_settings())
            with app.state.session_factory() as db:
                self.assertTrue(db.info["source_wallet_enabled"])
                self.assertTrue(db.info["default_collection_access"])
                self.assertTrue(db.info["real_wallet_enabled"])
            self.assertFalse(app.state.settings.local_google_trial)
            self.assertFalse(app.state.settings.source_wallet_trial)
        finally:
            engine.dispose()

    def test_schema_gate_is_read_only_and_rejects_old_revision(self):
        factory = MagicMock()
        db = factory.return_value.__enter__.return_value
        db.get_bind.return_value.dialect.name = "postgresql"
        inspector = MagicMock()
        inspector.get_columns.side_effect = lambda name, schema: [
            {"name": column} for column in Base.metadata.tables[name].columns.keys()]
        db.execute.return_value.scalars.return_value = ["20261003_0010"]
        with patch("qd766.backend.wallet_runtime.inspect", return_value=inspector):
            with self.assertRaises(ValueError):
                verify_real_wallet_schema(factory)
        commands = [str(call.args[0]) for call in db.execute.call_args_list]
        self.assertEqual(commands[0], "SET TRANSACTION READ ONLY")
        self.assertFalse(any(command.startswith(("INSERT", "UPDATE", "DELETE", "CREATE")) for command in commands))
        db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
