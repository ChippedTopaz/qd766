import unittest
from datetime import date
from stage_historical_recrawl import periods_for, score_diff, sql_guard


class StagedRecrawlTests(unittest.TestCase):
    def test_scope(self):
        periods = periods_for(date(2026, 10, 16))
        self.assertEqual(len(periods), 15)
        self.assertEqual([(p.type, p.value) for p in periods[:10]], [('month', m) for m in range(1, 11)])
        self.assertEqual([(p.type, p.value) for p in periods[10:]], [('quarter', q) for q in range(1, 5)] + [('year', None)])
        self.assertEqual(len(periods) * 35, 525)
        self.assertEqual(len(periods) * 205, 3075)

    def test_no_publication_sql(self):
        for sql in ['SELECT * FROM snapshots', 'SET TRANSACTION READ ONLY', 'UPDATE collection_controls SET lease_locked_at=%s WHERE key=%s']:
            sql_guard(None, None, sql, None, None, False)
        for table in ['snapshots', 'national_summary_snapshots', 'daily_observations', 'credit_ledger_entries', 'source_monitor_alerts']:
            for verb in ['INSERT INTO', 'DELETE FROM', 'UPDATE']:
                with self.assertRaises(RuntimeError):
                    sql_guard(None, None, f'{verb} {table} SET id=1', None, None, False)

    def test_difference(self):
        before = {'group': {'unit': {'score': 1, 'maximum': 6}}}
        self.assertEqual(score_diff(before, before), [])
        after = {'group': {'unit': {'score': 2, 'maximum': 6}, 'added': {'score': 0, 'maximum': 6}}}
        result = score_diff(before, after)
        self.assertEqual(len(result), 2)
        self.assertEqual(next(r for r in result if r['departmentId'] == 'unit')['before']['score'], 1)
        self.assertEqual(before['group']['unit']['score'], 1)


if __name__ == '__main__':
    unittest.main()
