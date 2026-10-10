#!/usr/bin/env python3
"""Local preview and read-only usage API. Runs only while this process is open."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

from sync_codex_usage import ROOT, atomic_write, find_codex, normalize, read_account_usage


class UsageHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path != '/api/token-usage':
            return super().do_GET()
        try:
            data = json.loads(self.server.snapshot.read_text())
            if data.get('schemaVersion') != 1 or not isinstance(data.get('days'), list):
                raise ValueError('Invalid snapshot')
            body = (json.dumps(data) + '\n').encode()
        except (OSError, ValueError):
            self.send_error(503, 'Usage snapshot unavailable')
            return
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


def refresh(snapshot, site_dir, binary=None):
    data = normalize(read_account_usage(find_codex(binary)))
    atomic_write(snapshot, data)
    atomic_write(site_dir / 'assets/data/codex-usage.json', data)
    return data


def refresh_loop(stop, interval, snapshot, site_dir, binary):
    while not stop.is_set():
        try:
            data = refresh(snapshot, site_dir, binary)
            print(f"Usage refreshed: {data['coverage']['reportedDays']} days; {data['syncedAt']}", flush=True)
        except Exception:
            # Do not log upstream responses, credentials or local account metadata.
            print('Usage refresh failed; retaining the last valid snapshot. Check local login.', flush=True)
        stop.wait(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4173)
    parser.add_argument('--site-dir', type=Path, default=ROOT / '_site')
    parser.add_argument('--refresh-seconds', type=int, default=3600)
    parser.add_argument('--codex-bin')
    parser.add_argument('--no-sync', action='store_true', help='Serve the existing snapshot without accessing the account')
    args = parser.parse_args()
    if args.refresh_seconds < 300:
        parser.error('--refresh-seconds must be at least 300')
    if not (args.site_dir / 'index.html').is_file():
        parser.error('Build the Jekyll preview first; _site/index.html is missing.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(UsageHandler, directory=str(args.site_dir)))
    server.snapshot = ROOT / 'assets/data/codex-usage.json'
    stop = threading.Event()
    worker = None
    if not args.no_sync:
        worker = threading.Thread(target=refresh_loop, args=(stop, args.refresh_seconds, server.snapshot, args.site_dir, args.codex_bin))
        worker.start()
    print(f'Preview: http://127.0.0.1:{args.port}/ | API: /api/token-usage', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
        if worker:
            worker.join()


if __name__ == '__main__':
    main()
