import importlib.util
import json
import unittest
from pathlib import Path

from qd766.backend.config import Settings

spec = importlib.util.spec_from_file_location("trial_readiness",
    Path(__file__).resolve().parents[1] / "tools" / "audit_trial_readiness.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ReadinessTest(unittest.TestCase):
    def test_default_office_is_not_public_ready(self):
        checks = audit.configuration_checks(Settings())
        for key in ("googleClientConfigured", "googleRedirectHTTPS",
                    "publicBoundaryEnabled", "loginRequired", "paidRequestsEnabled"):
            self.assertFalse(checks[key])

    def test_config_output_never_contains_credentials(self):
        checks = audit.configuration_checks(Settings(
            google_client_id="private-id", google_client_secret="private-secret",
            google_redirect_uri="https://backend.example/api/v1/auth/google/callback"))
        self.assertTrue(checks["googleClientConfigured"])
        self.assertTrue(checks["googleRedirectHTTPS"])
        output = json.dumps(checks)
        for value in ("private-id", "private-secret", "backend.example"):
            self.assertNotIn(value, output)

    def test_callback_with_query_is_not_https_ready(self):
        checks = audit.configuration_checks(Settings(
            google_redirect_uri="https://backend.example/api/v1/auth/google/callback?code=secret"))
        self.assertFalse(checks["googleRedirectHTTPS"])
