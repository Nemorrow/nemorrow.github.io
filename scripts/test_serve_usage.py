import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from serve_usage import refresh


class RefreshTests(unittest.TestCase):
    def test_failed_refresh_preserves_both_snapshots(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot = root / 'source.json'
            target = root / 'assets/data/codex-usage.json'
            target.parent.mkdir(parents=True)
            snapshot.write_text('{"old":true}')
            target.write_text('{"old":true}')
            with patch('serve_usage.find_codex', return_value='unused'), patch('serve_usage.read_account_usage', side_effect=ValueError('offline')):
                with self.assertRaises(ValueError):
                    refresh(snapshot, root)
            self.assertEqual(snapshot.read_text(), '{"old":true}')
            self.assertEqual(target.read_text(), '{"old":true}')

    def test_success_exports_only_normalized_data_to_both_locations(self):
        raw = {'summary': {'lifetimeTokens': 1200000}, 'dailyUsageBuckets': [{'startDate': '2026-10-09', 'tokens': 1200000}], 'accountId': 'do-not-export'}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot = root / 'source.json'
            with patch('serve_usage.find_codex', return_value='unused'), patch('serve_usage.read_account_usage', return_value=raw):
                refresh(snapshot, root)
            self.assertEqual(snapshot.read_bytes(), (root / 'assets/data/codex-usage.json').read_bytes())
            self.assertNotIn('do-not-export', snapshot.read_text())
            self.assertEqual(json.loads(snapshot.read_text())['days'][0]['tokens'], 1200000)


if __name__ == '__main__':
    unittest.main()
