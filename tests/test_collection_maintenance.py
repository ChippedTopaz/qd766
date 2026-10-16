import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from qd766.backend.collection_maintenance import user_collection_paused


class CollectionMaintenanceTests(unittest.TestCase):
    def test_gate_can_be_enabled_and_disabled_without_source_or_database(self):
        runtime = Path(__file__).resolve().parents[1] / '.tmp-maintenance-tests'
        runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as directory:
            marker = Path(directory) / 'paused.json'
            with patch('qd766.backend.collection_maintenance.PAUSE_FILE', marker):
                self.assertFalse(user_collection_paused())
                marker.write_text('not-json', encoding='utf-8')
                self.assertTrue(user_collection_paused(), 'Malformed metadata still pauses')
                marker.unlink()
                self.assertFalse(user_collection_paused())
