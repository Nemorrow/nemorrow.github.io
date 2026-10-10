#!/usr/bin/env python3
"""Local macOS scheduled exporter. Uses existing Codex and Git credentials only."""
import argparse
from datetime import datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo
from sync_codex_usage import find_codex, read_account_usage, normalize, atomic_write

ZONE = ZoneInfo('Asia/Shanghai')
SLOTS = ((0, 5), (6, 0), (18, 0))
FILES = ('assets/data/codex-usage.json', '_data/token_usage_snapshot.json')
REPO_URL = 'https://github.com/Nemorrow/nemorrow.github.io.git'


def due_slot(now):
    now = now.astimezone(ZONE)
    candidates = [now.replace(hour=h, minute=m, second=0, microsecond=0) for h, m in SLOTS]
    return max(x for x in candidates + [candidates[-1] - timedelta(days=1)] if x <= now).isoformat()


def semantic(data):
    return {'schemaVersion': data.get('schemaVersion'), 'days': data.get('days'), 'summary': data.get('summary')}


def run(args):
    state = args.state_dir.expanduser().resolve()
    state.mkdir(parents=True, exist_ok=True)
    os.chmod(state, 0o700)
    with (state / 'sync.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        status_path = state / 'status.json'
        status = json.loads(status_path.read_text()) if status_path.exists() else {}
        slot = due_slot(datetime.now(ZONE))
        if not args.force and status.get('lastSuccessfulSlot', '') >= slot:
            return
        checkout = state / 'checkout'
        env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
        def git(*parts, root=None):
            result = subprocess.run(['git', '-C', str(root or checkout), *parts], env=env,
                                    capture_output=True, text=True, timeout=120)
            if result.returncode:
                # Do not copy remote output or credential-helper details into logs.
                raise RuntimeError(f'Git {parts[0]} failed; check network and GitHub CLI authentication.')
            return result.stdout.strip()
        try:
            identity = subprocess.run(['gh', 'api', 'user', '--jq', '.login'], env=env,
                                      capture_output=True, text=True, timeout=30)
            if identity.returncode or identity.stdout.strip().lower() != 'nemorrow':
                raise RuntimeError('GitHub CLI must be logged into Nemorrow before automatic sync.')
            if not checkout.exists():
                git('clone', '--branch', 'master', '--single-branch', REPO_URL, str(checkout), root=state)
            if git('remote', 'get-url', 'origin') != REPO_URL:
                raise RuntimeError('Unexpected remote in dedicated checkout.')
            if git('status', '--porcelain'):
                raise RuntimeError('Dedicated checkout has uncommitted changes; inspect before retrying.')
            # Scope the credential helper to this dedicated checkout; gh uses the OS keychain.
            git('config', 'credential.https://github.com.helper', '!gh auth git-credential')
            git('config', 'user.name', 'Nemorrow')
            git('config', 'user.email', '135946125+Nemorrow@users.noreply.github.com')
            git('fetch', 'origin', 'master')
            ahead = int(git('rev-list', '--count', 'origin/master..HEAD'))
            if ahead:
                changed = set(git('diff', '--name-only', 'origin/master...HEAD').splitlines())
                if changed - set(FILES):
                    raise RuntimeError('Pending commits include non-usage files; refusing automatic push.')
                git('rebase', 'origin/master')
                git('push', 'origin', 'HEAD:master')
            else:
                git('merge', '--ff-only', 'origin/master')
            data = normalize(read_account_usage(find_codex()))
            current = json.loads((checkout / FILES[0]).read_text())
            embedded = json.loads((checkout / FILES[1]).read_text())
            changed = semantic(data) != semantic(current) or semantic(data) != semantic(embedded)
            if changed:
                for path in FILES:
                    atomic_write(checkout / path, data)
                git('add', '--', *FILES)
                git('commit', '-m', 'chore: update token usage')
                git('push', 'origin', 'HEAD:master')
            status.update(lastSuccessfulSlot=slot, lastSuccess=datetime.now(ZONE).isoformat(),
                          lastResult='updated' if changed else 'unchanged', lastError=None)
            atomic_write(status_path, status)
            print(f"{status['lastSuccess']} {status['lastResult']}", flush=True)
        except Exception as error:
            status.update(lastAttempt=datetime.now(ZONE).isoformat(), lastError=str(error))
            atomic_write(status_path, status)
            print(f"Sync failed: {error}", flush=True)
            raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', required=True, type=Path)
    parser.add_argument('--force', action='store_true', help='Run even if this slot already succeeded.')
    run(parser.parse_args())
