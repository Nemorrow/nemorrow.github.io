#!/usr/bin/env python3
"""Export account-wide Codex activity via the locally authenticated App Server.
Standard library only; never reads, prints, or copies authentication credentials.
"""
import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def find_codex(explicit=None):
    candidates = [explicit or os.environ.get('CODEX_BIN')]
    for app in ('Codex', 'ChatGPT'):
        candidates.append(f'/Applications/{app}.app/Contents/Resources/codex-cli/bin/codex')
        candidates.append(f'/Applications/{app}.app/Contents/Resources/codex')
    candidates.append(shutil.which('codex'))
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    raise ValueError('Codex CLI not found. Set CODEX_BIN or pass --codex-bin.')


def read_account_usage(binary, socket_path=None, timeout=60):
    command = [binary, 'app-server']
    command += ['proxy', '--sock', socket_path] if socket_path else ['--stdio']
    # Authentication stays inside Codex. Suppress server logs, which can contain local metadata.
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, bufsize=0)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    buffered = b''

    def send(message):
        process.stdin.write((json.dumps(message) + '\n').encode())
        process.stdin.flush()

    def receive(request_id):
        nonlocal buffered
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            while b'\n' in buffered:
                line, buffered = buffered.split(b'\n', 1)
                message = json.loads(line)
                if message.get('id') != request_id:
                    continue
                if 'error' in message:
                    code = message['error'].get('code', 'unknown')
                    raise ValueError(f'App Server request failed (code {code}). Check local Codex login and version.')
                return message['result']
            if selector.select(min(1, max(0, deadline - time.monotonic()))):
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    raise ValueError('App Server exited. Check the CLI path, local login, and permissions.')
                buffered += chunk
        raise ValueError('App Server request timed out; existing JSON was preserved.')

    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'personal_site_usage_sync', 'version': '1.0.0'},
            'capabilities': {'experimentalApi': True}}})
        receive(1)
        send({'method': 'initialized'})
        send({'id': 2, 'method': 'account/usage/read', 'params': {}})
        return receive(2)
    finally:
        selector.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()


def nonnegative_int(value):
    return type(value) is int and 0 <= value <= 9007199254740991


def normalize(raw):
    buckets = raw.get('dailyUsageBuckets')
    if not isinstance(buckets, list) or not buckets:
        raise ValueError('Daily usage is unavailable or empty; existing JSON was preserved.')
    days = {}
    for bucket in buckets:
        day = bucket.get('startDate')
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError('Invalid date in daily usage.')
        tokens = bucket.get('tokens')
        if not nonnegative_int(tokens) or day in days:
            raise ValueError('Invalid token count or duplicate daily bucket.')
        days[day] = tokens
    ordered = sorted(days)
    total = sum(days.values())
    if not nonnegative_int(total):
        raise ValueError('Token total exceeds the supported safe integer range.')
    summary = raw.get('summary', {})
    if not isinstance(summary, dict):
        raise ValueError('Invalid account summary.')
    lifetime = summary.get('lifetimeTokens')
    if lifetime is not None and not nonnegative_int(lifetime):
        raise ValueError('Invalid lifetime token count.')
    span = (date.fromisoformat(ordered[-1]) - date.fromisoformat(ordered[0])).days + 1
    return {
        'schemaVersion': 1,
        'syncedAt': datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
        'source': {'method': 'account/usage/read', 'scope': 'account-wide',
                   'dateTimezone': 'unspecified by source',
                   'tokenDefinition': 'Aggregate tokens reported by Codex; input/output/cache composition unspecified.',
                   'missingDays': 'unknown, not zero', 'latestDayMayBePartial': True},
        'coverage': {'firstDate': ordered[0], 'lastDate': ordered[-1],
                     'reportedDays': len(days), 'unreportedDaysInRange': span - len(days)},
        'summary': {'reportedTokens': total, 'lifetimeTokens': lifetime,
                    'dailySumMatchesLifetime': total == lifetime if lifetime is not None else None,
                    'peakReportedDailyTokens': max(days.values())},
        'days': [{'date': day, 'tokens': days[day]} for day in ordered]
    }


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.codex-usage-', suffix='.tmp', delete=False) as handle:
            temp = Path(handle.name)
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp and temp.exists():
            temp.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-bin', help='Path to a working local Codex CLI')
    parser.add_argument('--socket', help='Optional existing App Server control socket')
    parser.add_argument('--output', type=Path, default=ROOT / 'assets/data/codex-usage.json')
    args = parser.parse_args()
    try:
        result = normalize(read_account_usage(find_codex(args.codex_bin), args.socket))
        atomic_write(args.output, result)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Sync failed: {error}\n')
    coverage = result['coverage']
    print(f"Saved {coverage['reportedDays']} daily records, {coverage['firstDate']} through "
          f"{coverage['lastDate']}, {result['summary']['reportedTokens']:,} tokens to {args.output}")


if __name__ == '__main__':
    main()
