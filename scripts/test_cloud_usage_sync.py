#!/usr/bin/env python3
"""Offline tests; fake App Server only, no account, credentials or GitHub calls."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cloud_usage_sync as sync

NOW = datetime(2026, 11, 3, 3, 30, tzinfo=timezone.utc)
HEAD = 'a' * 40


def snapshot(tokens=100, at=NOW):
    return sync.normalize_usage({'dailyUsageBuckets': [{'startDate': '2026-11-01', 'tokens': tokens}],
                                 'summary': {'lifetimeTokens': tokens}}, at)


class PlanTests(unittest.TestCase):
    def test_fresh_unchanged_has_no_write_paths_despite_timestamp_change(self):
        old = snapshot(at=NOW - timedelta(days=1))
        plan = sync.prepare_plan(snapshot(), old, old, HEAD, now=NOW)
        self.assertEqual(plan['outcome'], 'unchanged')
        self.assertEqual(plan['writePaths'], [])
        self.assertEqual(plan['expectedSha'], HEAD)
        self.assertIs(plan['force'], False)

    def test_real_change_and_official_downward_revision_are_allowed(self):
        old = snapshot(tokens=200, at=NOW - timedelta(hours=1))
        plan = sync.prepare_plan(snapshot(tokens=100), old, old, HEAD, now=NOW)
        self.assertEqual(plan['outcome'], 'change')
        self.assertEqual(plan['writePaths'], list(sync.DATA_PATHS))

    def test_old_candidate_cannot_overwrite_newer_published_data(self):
        candidate = snapshot(tokens=300, at=NOW - timedelta(minutes=1))
        current = snapshot(tokens=200)
        plan = sync.prepare_plan(candidate, current, current, HEAD, now=NOW)
        self.assertEqual(plan['outcome'], 'stale')
        self.assertEqual(plan['writePaths'], [])

    def test_older_matching_data_is_still_marked_stale(self):
        candidate = snapshot(at=NOW - timedelta(minutes=1))
        current = snapshot()
        plan = sync.prepare_plan(candidate, current, current, HEAD, now=NOW)
        self.assertEqual(plan['outcome'], 'stale')
        self.assertEqual(plan['writePaths'], [])

    def test_inconsistent_snapshots_need_repair_at_fresh_read_time(self):
        left = snapshot(tokens=10, at=NOW - timedelta(hours=2))
        right = snapshot(tokens=100, at=NOW - timedelta(hours=1))
        self.assertEqual(sync.prepare_plan(snapshot(), left, right, HEAD, now=NOW)['outcome'], 'change')

    def test_successful_commit_followed_by_lost_local_receipt_is_idempotent(self):
        old = snapshot(tokens=10, at=NOW - timedelta(hours=1))
        candidate = snapshot(tokens=100)
        first = sync.prepare_plan(candidate, old, old, HEAD, now=NOW)
        self.assertEqual(first['outcome'], 'change')
        # Publication survived; a subsequent invocation has no previous receipt.
        after = sync.prepare_plan(snapshot(at=NOW + timedelta(minutes=1)), candidate,
                                  candidate, 'b' * 40, now=NOW + timedelta(minutes=1))
        self.assertEqual(after['outcome'], 'unchanged')
        self.assertEqual(after['writePaths'], [])

    def test_cas_conflict_must_use_the_new_head_and_snapshot(self):
        candidate = snapshot(tokens=110, at=NOW - timedelta(minutes=1))
        old = snapshot(tokens=100, at=NOW - timedelta(hours=1))
        self.assertEqual(sync.prepare_plan(candidate, old, old, HEAD, now=NOW)['outcome'], 'change')
        new_head = 'b' * 40
        new_data = snapshot(tokens=120)
        plan = sync.prepare_plan(candidate, new_data, new_data, new_head, now=NOW)
        self.assertEqual(plan['outcome'], 'stale')
        self.assertEqual(plan['expectedSha'], new_head)

    def test_equal_timestamp_with_different_data_is_ambiguous(self):
        with self.assertRaisesRegex(sync.SyncError, 'ambiguous_source_order'):
            sync.prepare_plan(snapshot(tokens=2), snapshot(), snapshot(), HEAD, now=NOW)

    def test_expired_and_future_candidates_are_rejected(self):
        old = snapshot(at=NOW - timedelta(days=1))
        for delta, error in ((timedelta(seconds=-601), 'candidate_expired'),
                             (timedelta(seconds=31), 'candidate_clock_skew')):
            with self.subTest(error=error), self.assertRaisesRegex(sync.SyncError, error):
                sync.prepare_plan(snapshot(at=NOW + delta), old, old, HEAD, now=NOW)

    def test_future_published_time_stops_without_writing(self):
        future = snapshot(at=NOW + timedelta(minutes=5))
        with self.assertRaisesRegex(sync.SyncError, 'published_clock_skew'):
            sync.prepare_plan(snapshot(), future, future, HEAD, now=NOW)

    def test_malformed_snapshot_and_head_are_rejected(self):
        for field in ('days', 'summary', 'coverage', 'source'):
            corrupt = snapshot()
            corrupt[field] = None
            with self.subTest(field=field), self.assertRaises(sync.SyncError):
                sync.prepare_plan(snapshot(), corrupt, snapshot(), HEAD, now=NOW)
        corrupt = snapshot(tokens=1)
        corrupt['summary']['reportedTokens'] = True
        with self.assertRaises(sync.SyncError):
            sync.validate_snapshot(corrupt)
        for head in ('master', 'a' * 39, 'A' * 40, None):
            with self.subTest(head=head), self.assertRaisesRegex(sync.SyncError, 'invalid_head_sha'):
                sync.prepare_plan(snapshot(), snapshot(), snapshot(), head, now=NOW)

    def test_duplicate_days_and_mismatched_lifetime_are_rejected(self):
        for raw in (
            {'dailyUsageBuckets': [{'startDate': '2026-11-01', 'tokens': 1}] * 2,
             'summary': {'lifetimeTokens': 2}},
            {'dailyUsageBuckets': [{'startDate': '2026-11-01', 'tokens': 1}],
             'summary': {'lifetimeTokens': 2}},
            {'dailyUsageBuckets': [{'startDate': '2026-11-01', 'tokens': 1}],
             'summary': {}},
        ):
            with self.subTest(raw=raw), self.assertRaises(sync.SyncError):
                sync.normalize_usage(raw, NOW)

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'data.json'
            p.write_text('{"schemaVersion": 1, "schemaVersion": 2}')
            with self.assertRaisesRegex(sync.SyncError, 'duplicate_json_key'):
                sync.load_json(p)

    def test_input_snapshots_are_not_mutated(self):
        candidate = snapshot()
        current = snapshot(at=NOW - timedelta(hours=1))
        before = deepcopy((candidate, current))
        sync.prepare_plan(candidate, current, current, HEAD, now=NOW)
        self.assertEqual((candidate, current), before)


class AppServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'existing-home'
        self.home.mkdir()
        self.marker = self.root / 'persistence-marker.json'
        self.marker.write_text('{"markerId":"test-marker"}')
        self.binary = self.root / 'fake-codex'
        self.calls = self.root / 'calls.jsonl'
        self.binary.write_text('#!' + sys.executable + '\n' + textwrap.dedent('''
            import json, os, sys, time
            mode = os.environ.get('FAKE_MODE', '')
            for line in sys.stdin:
                request = json.loads(line)
                with open(os.environ['FAKE_CALLS'], 'a') as log:
                    log.write(json.dumps({'method': request['method'], 'params': request.get('params'),
                                          'home': os.environ.get('CODEX_HOME'),
                                          'rustLog': os.environ.get('RUST_LOG')}) + '\\n')
                method = request['method']
                if method == 'initialized':
                    continue
                if mode == 'timeout':
                    time.sleep(30)
                if method == 'initialize':
                    result = {}
                elif method == 'account/read':
                    account = {'type': 'chatgpt', 'email': 'expected@example.test', 'planType': 'pro'}
                    if mode == 'wrong-account': account['email'] = 'another@example.test'
                    if mode == 'wrong-plan': account['planType'] = 'plus'
                    if mode == 'api-key': account['type'] = 'apiKey'
                    result = {'account': account, 'requiresOpenaiAuth': True}
                elif method == 'account/usage/read':
                    if mode == 'rpc-error':
                        print(json.dumps({'id': request['id'], 'error': {'code': -32001,
                              'message': 'PRIVATE_SERVER_ERROR_DO_NOT_PRINT'}}), flush=True)
                        continue
                    total = 101 if mode == 'bad-sum' else 100
                    result = {'dailyUsageBuckets': [{'startDate': '2026-11-01', 'tokens': 100}],
                              'summary': {'lifetimeTokens': total}}
                print(json.dumps({'id': request['id'], 'result': result}), flush=True)
        '''))
        self.binary.chmod(0o755)
        self.env = patch.dict(os.environ, FAKE_CALLS=str(self.calls), FAKE_MODE='')
        self.env.start()
        self.addCleanup(self.env.stop)

    def read_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def args(self, output='result'):
        return argparse.Namespace(codex_home=self.home, codex_bin=str(self.binary),
                                  marker_file=self.marker, marker_key='markerId',
                                  expected_marker='test-marker', expected_email='expected@example.test',
                                  output_dir=self.root / output)

    def test_same_session_identity_before_usage_and_no_account_fields_in_output(self):
        with patch.object(sync, 'utc_now', side_effect=[NOW, NOW + timedelta(seconds=1)]):
            result = sync.collect(self.args())
        calls = self.read_calls()
        self.assertEqual([call['method'] for call in calls],
                         ['initialize', 'initialized', 'account/read', 'account/usage/read'])
        self.assertEqual(calls[2]['params'], {'refreshToken': False})
        self.assertTrue(all(call['home'] == str(self.home.resolve()) for call in calls))
        self.assertTrue(all(call['rustLog'] == 'off' for call in calls))
        self.assertTrue(calls[0]['params']['capabilities']['explicitGatewayOauth'])
        candidate = sync.load_json(self.args().output_dir / 'candidate.json')
        self.assertEqual(candidate['syncedAt'], sync.timestamp(NOW))
        self.assertTrue(result['identityVerified'])
        for p in self.args().output_dir.iterdir():
            self.assertNotIn('expected@example.test', p.read_text())
            self.assertNotIn('planType', p.read_text())

    def test_account_and_plan_mismatch_stop_before_usage(self):
        for mode in ('wrong-account', 'wrong-plan', 'api-key'):
            self.calls.unlink(missing_ok=True)
            with self.subTest(mode=mode), patch.dict(os.environ, FAKE_MODE=mode):
                with self.assertRaises(sync.SyncError):
                    sync.read_verified_usage(str(self.binary), self.home, 'expected@example.test')
                self.assertNotIn('account/usage/read', [call['method'] for call in self.read_calls()])

    def test_rpc_error_is_redacted_at_cli_boundary(self):
        command = [sys.executable, str(Path(sync.__file__)), 'collect', '--codex-home', str(self.home),
                   '--codex-bin', str(self.binary), '--expected-email', 'expected@example.test',
                   '--marker-file', str(self.marker), '--expected-marker', 'test-marker',
                   '--output-dir', str(self.root / 'rpc-output')]
        with patch.dict(os.environ, FAKE_MODE='rpc-error'):
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['rpcCode'], -32001)
        self.assertNotIn('PRIVATE_SERVER_ERROR', result.stdout + result.stderr)
        self.assertNotIn('expected@example.test', result.stdout + result.stderr)
        self.assertFalse((self.root / 'rpc-output' / 'candidate.json').exists())

    def test_timeout_reaps_child(self):
        with patch.dict(os.environ, FAKE_MODE='timeout'):
            started = sync.time.monotonic()
            with self.assertRaisesRegex(sync.SyncError, 'app_server_timeout'):
                sync.read_verified_usage(str(self.binary), self.home, 'expected@example.test', timeout=0.05)
            self.assertLess(sync.time.monotonic() - started, 4)

    def test_bad_sum_does_not_create_candidate(self):
        with patch.dict(os.environ, FAKE_MODE='bad-sum'), self.assertRaises(sync.SyncError):
            sync.collect(self.args())
        self.assertFalse((self.args().output_dir / 'candidate.json').exists())

    def test_existing_output_or_invalid_marker_stops_before_rpc(self):
        args = self.args()
        args.output_dir.mkdir()
        with self.assertRaises(FileExistsError):
            sync.collect(args)
        args = self.args('other')
        args.expected_marker = 'wrong'
        with self.assertRaisesRegex(sync.SyncError, 'marker_mismatch'):
            sync.collect(args)
        self.assertFalse(self.calls.exists())

    def test_old_or_missing_ledger_has_no_effect(self):
        stale = self.root / 'sync-state'
        stale.mkdir()
        (stale / 'state.json').write_text('{"activeRun":"old-incomplete-run"}')
        sync.collect(self.args())
        (stale / 'state.json').unlink()
        sync.collect(self.args('second-result'))
        self.assertEqual((stale / 'state.json').exists(), False)
        self.assertEqual(len([call for call in self.read_calls() if call['method'] == 'account/usage/read']), 2)

    def test_marker_symlink_is_not_read(self):
        self.marker.unlink()
        target = self.root / 'another-marker.json'
        target.write_text('{"markerId":"test-marker"}')
        self.marker.symlink_to(target)
        with self.assertRaisesRegex(sync.SyncError, 'invalid_existing_configuration'):
            sync.collect(self.args())
        self.assertFalse(self.calls.exists())


if __name__ == '__main__':
    unittest.main()
