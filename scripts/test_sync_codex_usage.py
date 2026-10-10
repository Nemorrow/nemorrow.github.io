import copy
import json
from pathlib import Path
import tempfile
import unittest
from sync_codex_usage import normalize, atomic_write


class UsageExportTests(unittest.TestCase):
    def setUp(self):
        self.raw = {'summary': {'lifetimeTokens': 12}, 'dailyUsageBuckets': [
            {'startDate': '2026-10-09', 'tokens': 12},
            {'startDate': '2026-10-07', 'tokens': 0}],
            'threadUsage': {'threadId': 'private-thread'}, 'accountId': 'private-account'}

    def test_sparse_days_and_zero_remain_distinct(self):
        data = normalize(self.raw)
        self.assertEqual(data['coverage']['unreportedDaysInRange'], 1)
        self.assertEqual(data['days'], [{'date': '2026-10-07', 'tokens': 0}, {'date': '2026-10-09', 'tokens': 12}])
        self.assertTrue(data['summary']['dailySumMatchesLifetime'])
        self.assertNotIn('private', json.dumps(data))

    def test_summary_range_mismatch_is_explicit(self):
        self.raw['summary']['lifetimeTokens'] = 50
        data = normalize(self.raw)
        self.assertEqual(data['summary']['reportedTokens'], 12)
        self.assertFalse(data['summary']['dailySumMatchesLifetime'])

    def test_invalid_data_cannot_replace_good_snapshot(self):
        bads = [None, [], [{'startDate': '2026-02-30', 'tokens': 1}],
                [{'startDate': '2026-10-09', 'tokens': -1}],
                [{'startDate': '2026-10-09', 'tokens': True}],
                [{'startDate': '2026-10-09', 'tokens': 1}] * 2]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'usage.json'
            atomic_write(path, normalize(self.raw))
            good = path.read_bytes()
            for bad in bads:
                raw = copy.deepcopy(self.raw)
                raw['dailyUsageBuckets'] = bad
                with self.assertRaises(ValueError):
                    atomic_write(path, normalize(raw))
                self.assertEqual(path.read_bytes(), good)


if __name__ == '__main__':
    unittest.main()
