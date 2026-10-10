# Token usage

The homepage reads its own `assets/data/codex-usage.json`. Jekyll embeds
`_data/token_usage_snapshot.json` for an immediate first visit. A newer browser
cache can render first; the site refreshes the repository JSON in the background
and every five minutes while visible. No independent storage or dot task is needed.

## Local scheduled synchronization

`scripts/scheduled_usage_sync.py --state-dir /ABSOLUTE/PRIVATE/STATE/DIRECTORY`

Run through a macOS LaunchAgent at 00:05, 06:00 and 18:00 (Asia/Shanghai).
RunAtLoad catches up after login; a 30-minute retry checks for missed/failed slots.
A successful slot is skipped on subsequent checks. After shutdown, it exports the
latest complete available history once instead of generating a commit per missed slot.
The computer must be logged in and online; it is not awakened or powered on by this job.

The job requires Python 3.9+, Codex/ChatGPT's bundled CLI and GitHub CLI (`gh`).
Authenticate Codex locally, then `gh auth login` as Nemorrow. Credentials remain in
Codex's normal auth storage and GitHub CLI's system keychain, never in this repo.

A dedicated checkout in the private state directory prevents interference with edits
in the development checkout. Each run fetches master, calls `account/usage/read`,
validates and sanitizes data, compares actual daily counts and summary, and updates
both JSON files together. A `syncedAt` change alone does not trigger a commit.
Only these two files may be committed, with message `chore: update token usage`.
Push triggers the existing GitHub Pages deployment. Failed pushes stay in the isolated
checkout for retry; divergent changes/conflicts stop safely without force-pushing.

`status.json` records the last successful slot and last error. `sync.log` and
`sync-error.log` are local. Use `--force` for a manual run of the current slot.
Keep the installed runner and its state directory at their configured paths.

## Data scope

The data is the authenticated account's `account/usage/read` response, not local
session-log estimates. Source dates and integer counts are preserved. Input/output/
cache breakdown, source timezone and full product coverage remain unspecified.
Missing dates display `0` but are not synthesized into records. The average uses
reported days; labels use e.g. `Sep 16 — 43.3M`.

## Preview and validation

`python3 scripts/serve_usage.py --no-sync` previews saved data on port 4173.
`python3 scripts/sync_codex_usage.py` manually exports a local snapshot without Git.
Tests: `python3 -m unittest discover -s scripts -p 'test_*.py'`.
