import unittest
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProductionTrialConfigTests(unittest.TestCase):
    def test_netlify_api_proxy_preserves_api_prefix_and_targets_only_public_https(self):
        config = tomllib.loads((ROOT / 'netlify.toml').read_text(encoding='utf-8'))
        proxy = next(rule for rule in config['redirects'] if rule['from'] == '/api/*')
        self.assertEqual(proxy['to'], 'https://api.bochiso766.com/api/:splat')
        self.assertEqual(proxy['status'], 200)
        self.assertIs(proxy['force'], True)
        self.assertNotIn('localhost', str(config))

    def test_public_task_is_separate_hidden_and_not_started_implicitly(self):
        script = (ROOT / 'tools/register_public_backend_task.ps1').read_text(encoding='utf-8')
        self.assertIn("$TaskName = 'QD766 Public Backend'", script)
        self.assertIn('-WindowStyle Hidden', script)
        self.assertIn('-ExecutionTimeLimit ([TimeSpan]::Zero)', script)
        self.assertIn('-LogonType Interactive', script)
        self.assertIn('Export-ScheduledTask', script)
        self.assertNotIn('Start-ScheduledTask', script)
        self.assertNotIn('Stop-Process', script)
        self.assertNotIn('register_windows_tasks.ps1', script)
