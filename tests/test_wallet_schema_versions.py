import unittest
from unittest.mock import MagicMock, patch
from qd766.backend.models import Base
from qd766.backend.wallet_runtime import verify_real_wallet_schema


class WalletSchemaVersionsTest(unittest.TestCase):
    def verify(self, version, missing=None, shared_registration=False):
        db=MagicMock(); db.get_bind.return_value.dialect.name='postgresql'
        db.execute.return_value.scalars.return_value=[version]
        factory=MagicMock(); factory.return_value.__enter__.return_value=db
        inspector=MagicMock()
        inspector.get_columns.side_effect=lambda name, **kwargs: [
            {'name':c} for c in Base.metadata.tables[name].columns.keys()
            if not (missing and name==missing)]
        with patch('qd766.backend.wallet_runtime.inspect',return_value=inspector):
            verify_real_wallet_schema(factory,shared_registration=shared_registration)

    def test_registration_requires_migrated_schema(self):
        with self.assertRaises(ValueError):self.verify('20261004_0015',shared_registration=True)
        self.verify('20261005_0017',shared_registration=True)

    def test_reviewed_versions(self):
        for version in ('20261004_0015','20261005_0016','20261005_0017','20261006_0018','20261007_0019','20261007_0020','20261007_0021','20261007_0022','20261007_0023'):
            with self.subTest(version=version):self.verify(version)

    def test_unknown_revision_rejected(self):
        with self.assertRaises(ValueError):self.verify('20261007_0024')
        with self.assertRaises(ValueError):self.verify('20261008_0025')

    def test_formula_upgrade_requires_all_previous_and_formula_tables(self):
        self.verify('20261008_0024',shared_registration=True)
        for table in ('formula_config_revisions','formula_config_head','trivia_questions',
                      'analysis_feature_control','credit_lots','daily_observations'):
            with self.subTest(table=table), self.assertRaises(ValueError):
                self.verify('20261008_0024',table)

    def test_public_registration_requires_new_profile_and_previous_tables(self):
        self.verify('20261009_0025',shared_registration=True)
        for table in ('login_attempts','trial_registrations','formula_config_head',
                      'trivia_answers','analysis_feature_control','analysis_queue_entries'):
            with self.subTest(table=table), self.assertRaises(ValueError):
                self.verify('20261009_0025',table)

    def test_trivia_tables_required_for_reviewed_upgrade(self):
        for table in ('trivia_questions','trivia_profiles','trivia_answers'):
            with self.assertRaises(ValueError):self.verify('20261007_0023',table)

    def test_analysis_table_required(self):
        with self.assertRaises(ValueError):self.verify('20261006_0018','gemini_analyses')
        with self.assertRaises(ValueError):self.verify('20261007_0019','analysis_queue_entries')
        with self.assertRaises(ValueError):self.verify('20261007_0020','analysis_config_revisions')
        with self.assertRaises(ValueError):self.verify('20261007_0020','analysis_config_head')
        with self.assertRaises(ValueError):self.verify('20261007_0021','analysis_group_config_revisions')
        with self.assertRaises(ValueError):self.verify('20261007_0022','analysis_feature_control')
        with self.assertRaises(ValueError):self.verify('20261007_0022','credit_lots')

    def test_missing_daily_table_columns_rejected(self):
        with self.assertRaises(ValueError):self.verify('20261005_0017','daily_observations')

    def test_missing_wallet_columns_rejected(self):
        with self.assertRaises(ValueError):self.verify('20261005_0017','credit_lots')
