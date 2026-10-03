import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

script = Path(__file__).resolve().parents[1] / "tools" / "test_postgresql_credits.py"
spec = importlib.util.spec_from_file_location("postgresql_credit_checks", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PostgreSQLCreditGuardTests(unittest.TestCase):
    def test_components_never_inherit_application_database_name(self):
        file = Mock()
        file.read_text.return_value = "QD766_DATABASE_NAME=production\nQD766_DATABASE_USER=test_role\nQD766_DATABASE_HOST=127.0.0.1"
        url = module.isolated_url(file)
        self.assertEqual(url.database, "qd766_credit_test")
        self.assertEqual(url.username, "test_role")

    def test_explicit_url_never_inherits_database_or_search_path_options(self):
        file = Mock()
        file.read_text.return_value = "QD766_DATABASE_URL=postgresql+psycopg://test_role:test_password@localhost/production?options=unsafe"
        url = module.isolated_url(file)
        self.assertEqual(url.database, "qd766_credit_test")
        self.assertFalse(url.query)

    def test_remote_host_and_production_database_rejected_before_connect(self):
        file = Mock()
        file.read_text.return_value = "QD766_DATABASE_HOST=external.example"
        with self.assertRaises(ValueError):
            module.isolated_url(file)
        from sqlalchemy.engine import make_url
        with self.assertRaises(ValueError):
            module.run_checks(make_url("postgresql+psycopg://localhost/qd766"))
