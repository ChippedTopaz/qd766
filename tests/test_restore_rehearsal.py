import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from rehearse_credit_restore import require_empty_database, restore_url, verified_backup


class RestoreRehearsalTests(unittest.TestCase):
    def test_target_never_source_or_existing_general_test_database(self):
        config = {"QD766_DATABASE_URL": "postgresql+psycopg://user@localhost/qd766"}
        for name in ("qd766", "qd766_credit_test", "postgres", 'qd766_restore_20261004_092135;DROP DATABASE qd766'):
            with self.assertRaises(ValueError):
                restore_url(config, name)
        target = restore_url(config, "qd766_restore_20261004_092135")
        self.assertEqual(target.database, "qd766_restore_20261004_092135")
        with self.assertRaises(ValueError):
            restore_url({"QD766_DATABASE_URL": str(target)}, target.database)

    def test_non_loopback_and_schema_options_rejected(self):
        for url in ("sqlite://", "postgresql+psycopg://user@remote/qd766",
                    "postgresql+psycopg://user@localhost/qd766?options=search_path"):
            with self.assertRaises(ValueError):
                restore_url({"QD766_DATABASE_URL": url}, "qd766_restore_20261004_092135")

    def test_nonempty_or_wrong_database_rejected_without_write(self):
        for identity, count in ((('qd766', True), 0),
                                (('qd766_restore_20261004_092135', False), 0),
                                (('qd766_restore_20261004_092135', True), 1)):
            engine = MagicMock()
            db = engine.connect.return_value.__enter__.return_value
            db.execute.return_value.one.return_value = identity
            db.scalar.side_effect = [count, 0]
            with self.assertRaises(ValueError):
                require_empty_database(engine, "qd766_restore_20261004_092135")
            db.commit.assert_not_called()

    def test_missing_dump_fails_before_connecting(self):
        with self.assertRaises(FileNotFoundError):
            verified_backup(Path("missing-backup-for-test.dump"), "0" * 64)


if __name__ == "__main__":
    unittest.main()
