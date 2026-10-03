import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_launcher', ROOT / 'tools/start_public_backend.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class PublicLoggingTests(unittest.TestCase):
    def test_background_logs_utf8_bounded_and_no_access_log(self):
        with patch.object(Path, 'mkdir'):
            config = launcher.background_log_config()
        handler = config['handlers']['file']
        self.assertEqual(handler['encoding'], 'utf-8')
        self.assertEqual(handler['class'], 'logging.handlers.RotatingFileHandler')
        self.assertEqual(handler['maxBytes'], 10 * 1024 * 1024)
        self.assertEqual(handler['backupCount'], 5)
        self.assertEqual(config['loggers']['uvicorn.access']['handlers'], [])
        self.assertFalse(config['loggers']['uvicorn.access']['propagate'])
        self.assertNotIn('google', str(config))
