import unittest
from datetime import datetime
from scheduled_usage_sync import due_slot, semantic, ZONE

class ScheduleTests(unittest.TestCase):
    def test_boundaries_and_catchup(self):
        for now, expected in [('2026-10-11T00:04:59','2026-10-10T12:00:00+08:00'),('2026-10-11T00:05:00','2026-10-11T00:05:00+08:00'),('2026-10-11T06:00:00','2026-10-11T00:05:00+08:00'),('2026-10-11T11:59:59','2026-10-11T00:05:00+08:00'),('2026-10-11T12:00:00','2026-10-11T12:00:00+08:00'),('2026-10-11T18:00:00','2026-10-11T12:00:00+08:00')]:
            self.assertEqual(due_slot(datetime.fromisoformat(now).replace(tzinfo=ZONE)), expected)
    def test_timestamp_only_does_not_commit(self):
        base={'schemaVersion':1,'days':[{'date':'2026-10-10','tokens':100}], 'summary':{'lifetimeTokens':100},'syncedAt':'2026-10-10T00:00:00Z'}
        self.assertEqual(semantic(base),semantic({**base,'syncedAt':'2026-10-11T00:00:00Z'}))
        self.assertNotEqual(semantic(base),semantic({**base,'days':[{'date':'2026-10-10','tokens':101}]}))
if __name__=='__main__': unittest.main()
