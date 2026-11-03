#!/usr/bin/env python3
"""Collect verified usage and prepare a GitHub CAS update without a local ledger.

This helper never contacts GitHub. The caller must fetch both published files at
one head SHA, then use expected_sha with force=false to publish a change plan.
Credentials remain inside the existing Codex App Server configuration.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import time

from sync_codex_usage import atomic_write, find_codex, nonnegative_int, normalize

PROTOCOL = 'published-snapshot-v1'
DATA_PATHS = ('assets/data/codex-usage.json', '_data/token_usage_snapshot.json')
MAX_CANDIDATE_AGE = 600
MAX_CLOCK_SKEW = 30
TIMESTAMP = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$')


class SyncError(Exception):
    """Only fixed codes, never server messages or user-provided values."""

    def __init__(self, code, rpc_code=None):
        super().__init__(code)
        self.code = code
        self.rpc_code = rpc_code if type(rpc_code) is int else None


def utc_now():
    return datetime.now(timezone.utc)


def timestamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def parse_timestamp(value):
    if not isinstance(value, str) or not TIMESTAMP.fullmatch(value):
        raise SyncError('invalid_timestamp')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        raise SyncError('invalid_timestamp') from None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SyncError('duplicate_json_key')
        result[key] = value
    return result


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    except (ValueError, UnicodeError):
        raise SyncError('invalid_json') from None


def normalize_usage(raw, requested_at):
    try:
        if not isinstance(raw, dict):
            raise SyncError('invalid_usage')
        result = normalize(raw)
        if not nonnegative_int(result['summary']['lifetimeTokens']):
            raise SyncError('invalid_usage')
        if result['summary']['dailySumMatchesLifetime'] is not True:
            raise SyncError('usage_sum_mismatch')
        result['syncedAt'] = timestamp(requested_at)
        return result
    except (ValueError, TypeError, KeyError, AttributeError):
        raise SyncError('invalid_usage') from None


def validate_snapshot(data):
    expected_keys = {'schemaVersion', 'syncedAt', 'source', 'coverage', 'summary', 'days'}
    if not isinstance(data, dict) or set(data) != expected_keys:
        raise SyncError('invalid_snapshot')
    if type(data['schemaVersion']) is not int or data['schemaVersion'] != 1:
        raise SyncError('invalid_snapshot')
    read_at = parse_timestamp(data['syncedAt'])
    days = data['days']
    if not isinstance(days, list) or not days:
        raise SyncError('invalid_snapshot')
    try:
        if any(not nonnegative_int(data['summary'][key]) for key in
               ('reportedTokens', 'lifetimeTokens', 'peakReportedDailyTokens')):
            raise SyncError('invalid_snapshot')
        if data['summary']['dailySumMatchesLifetime'] is not True:
            raise SyncError('invalid_snapshot')
        if any(not nonnegative_int(data['coverage'][key]) for key in
               ('reportedDays', 'unreportedDaysInRange')):
            raise SyncError('invalid_snapshot')
        if data['source']['latestDayMayBePartial'] is not True:
            raise SyncError('invalid_snapshot')
        if any(not isinstance(day, dict) or set(day) != {'date', 'tokens'} for day in days):
            raise SyncError('invalid_snapshot')
        raw = {'dailyUsageBuckets': [{'startDate': day['date'], 'tokens': day['tokens']} for day in days],
               'summary': {'lifetimeTokens': data['summary']['lifetimeTokens']}}
        canonical = normalize_usage(raw, read_at)
        if any(data[key] != canonical[key] for key in ('days', 'summary', 'coverage', 'source')):
            raise SyncError('invalid_snapshot')
    except (KeyError, TypeError):
        raise SyncError('invalid_snapshot') from None
    return {key: data[key] for key in ('schemaVersion', 'days', 'summary')}, read_at


def read_verified_usage(binary, codex_home, expected_email, timeout=90):
    """Use one bounded session; discard every account field after validation."""
    env = dict(os.environ, CODEX_HOME=str(codex_home), RUST_LOG='off')
    process = subprocess.Popen([binary, 'app-server', '--stdio', '-c', 'analytics.enabled=false'], env=env,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, bufsize=0)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    buffered = b''
    deadline = time.monotonic() + timeout

    def send(message):
        try:
            process.stdin.write((json.dumps(message) + '\n').encode())
            process.stdin.flush()
        except (BrokenPipeError, OSError):
            raise SyncError('app_server_exited') from None

    def receive(request_id):
        nonlocal buffered
        while time.monotonic() < deadline:
            while b'\n' in buffered:
                line, buffered = buffered.split(b'\n', 1)
                try:
                    message = json.loads(line, object_pairs_hook=unique_object)
                except (ValueError, UnicodeError):
                    raise SyncError('invalid_rpc_response') from None
                if not isinstance(message, dict):
                    raise SyncError('invalid_rpc_response')
                if message.get('id') != request_id:
                    continue
                if 'error' in message:
                    error = message['error']
                    code = error.get('code') if isinstance(error, dict) else None
                    raise SyncError('app_server_rpc_error', code)
                if 'result' not in message:
                    raise SyncError('invalid_rpc_response')
                return message['result']
            if selector.select(min(0.2, max(0, deadline - time.monotonic()))):
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    raise SyncError('app_server_exited')
                buffered += chunk
                if len(buffered) > 8 * 1024 * 1024:
                    raise SyncError('rpc_response_too_large')
        raise SyncError('app_server_timeout')

    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'homepage_cloud_usage_sync', 'version': '2.0.0'},
            'capabilities': {'experimentalApi': True, 'explicitGatewayOauth': True}}})
        receive(1)
        send({'method': 'initialized'})
        send({'id': 2, 'method': 'account/read', 'params': {'refreshToken': False}})
        account_result = receive(2)
        account = account_result.get('account') if isinstance(account_result, dict) else None
        if not isinstance(account, dict) or account.get('type') != 'chatgpt':
            raise SyncError('account_identity_mismatch')
        if account.get('email') != expected_email:
            raise SyncError('account_identity_mismatch')
        if account.get('planType') != 'pro':
            raise SyncError('account_plan_mismatch')
        requested_at = utc_now()
        send({'id': 3, 'method': 'account/usage/read', 'params': {}})
        raw = receive(3)
        received_at = utc_now()
        return normalize_usage(raw, requested_at), received_at
    finally:
        selector.close()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        process.stdin.close()
        process.stdout.close()


def collect(args):
    home = args.codex_home.resolve(strict=True)
    if (not home.is_dir() or args.marker_file.name != 'persistence-marker.json'
            or args.marker_file.is_symlink()):
        raise SyncError('invalid_existing_configuration')
    marker = load_json(args.marker_file)
    if not isinstance(marker, dict) or marker.get(args.marker_key) != args.expected_marker:
        raise SyncError('marker_mismatch')
    binary = find_codex(args.codex_bin)
    if args.output_dir.is_symlink():
        raise SyncError('invalid_output_directory')
    args.output_dir.mkdir(mode=0o700, exist_ok=False)
    data, received_at = read_verified_usage(binary, home, args.expected_email)
    atomic_write(args.output_dir / 'candidate.json', data)
    receipt = {'protocol': PROTOCOL, 'status': 'passed', 'identityVerified': True,
               'sourceReadAt': data['syncedAt'], 'sourceReceivedAt': timestamp(received_at),
               'sourceLastDate': data['coverage']['lastDate'],
               'sourceDays': data['coverage']['reportedDays'],
               'sourceLifetimeTokens': data['summary']['lifetimeTokens'],
               'candidateFile': 'candidate.json'}
    atomic_write(args.output_dir / 'receipt.json', receipt)
    return receipt


def prepare_plan(candidate, published, embedded, head_sha, now=None):
    if not isinstance(head_sha, str) or not re.fullmatch('[0-9a-f]{40}', head_sha):
        raise SyncError('invalid_head_sha')
    candidate_semantic, candidate_time = validate_snapshot(candidate)
    existing = [validate_snapshot(data) for data in (published, embedded)]
    now = now or utc_now()
    age = (now - candidate_time).total_seconds()
    if age < -MAX_CLOCK_SKEW:
        raise SyncError('candidate_clock_skew')
    if age > MAX_CANDIDATE_AGE:
        raise SyncError('candidate_expired')
    if any((read_at - now).total_seconds() > MAX_CLOCK_SKEW for _, read_at in existing):
        raise SyncError('published_clock_skew')
    unchanged = all(semantic == candidate_semantic for semantic, _ in existing)
    if candidate_time < max(read_at for _, read_at in existing):
        outcome = 'stale'
    elif unchanged:
        outcome = 'unchanged'
    elif any(candidate_time == read_at and semantic != candidate_semantic for semantic, read_at in existing):
        raise SyncError('ambiguous_source_order')
    else:
        outcome = 'change'
    serialized = json.dumps(candidate, indent=2, ensure_ascii=False) + '\n'
    semantic_json = json.dumps(candidate_semantic, sort_keys=True, separators=(',', ':'))
    return {'protocol': PROTOCOL, 'status': 'passed', 'outcome': outcome,
            'headSha': head_sha, 'sourceReadAt': candidate['syncedAt'],
            'sourceHash': hashlib.sha256(semantic_json.encode()).hexdigest(),
            'candidateSha256': hashlib.sha256(serialized.encode()).hexdigest(),
            'writePaths': list(DATA_PATHS) if outcome == 'change' else [],
            'candidateFile': 'candidate.json', 'force': False, 'expectedSha': head_sha}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    source = commands.add_parser('collect')
    source.add_argument('--codex-home', type=Path, required=True)
    source.add_argument('--codex-bin')
    source.add_argument('--expected-email', required=True)
    source.add_argument('--marker-file', type=Path, required=True)
    source.add_argument('--marker-key', default='markerId')
    source.add_argument('--expected-marker', required=True)
    source.add_argument('--output-dir', type=Path, required=True)
    plan = commands.add_parser('plan')
    for name in ('candidate', 'published', 'embedded', 'output-dir'):
        plan.add_argument('--' + name, type=Path, required=True)
    plan.add_argument('--head-sha', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'collect':
            result = collect(args)
        else:
            result = prepare_plan(load_json(args.candidate), load_json(args.published),
                                  load_json(args.embedded), args.head_sha)
            if args.output_dir.is_symlink():
                raise SyncError('invalid_output_directory')
            args.output_dir.mkdir(mode=0o700, exist_ok=True)
            atomic_write(args.output_dir / 'decision.json', result)
    except SyncError as error:
        result = {'protocol': PROTOCOL, 'status': 'error', 'error': error.code}
        if error.rpc_code is not None:
            result['rpcCode'] = error.rpc_code
        print(json.dumps(result))
        return 1
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print(json.dumps({'protocol': PROTOCOL, 'status': 'error', 'error': 'local_io_or_configuration_error'}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
