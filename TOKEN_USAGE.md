# Token usage

The homepage displays an account-level daily token snapshot, with no product name in
its visible text. JSON counts retain their exact integer values; day labels round to
one decimal million (`180.7M`). Missing days remain distinct from explicit zero counts.
The calendar covers approximately six months. Total tokens and the average cover all
returned history; the average divides by reported days only.

## Refresh and preview

- One refresh: `python3 scripts/sync_codex_usage.py`
- Preview with hourly refresh: `python3 scripts/serve_usage.py`
- Preview without account access: `python3 scripts/serve_usage.py --no-sync`
- Local page: http://127.0.0.1:4173/
- Local read-only API: http://127.0.0.1:4173/api/token-usage

The service runs only while its process is open. It refreshes at startup and hourly;
the visible browser tab checks for updates every five minutes. Stop with Ctrl-C.
There is no system scheduler, auto-start, remote upload, commit, push, or deployment.
The supplied `Preview.command` launches this service against the included `_site/`.

The exporter locates the desktop-bundled CLI on macOS, then `codex` on PATH; override
with `--codex-bin` or `CODEX_BIN`. Authentication stays inside the locally authenticated
App Server. The site never receives credentials. Only allowlisted aggregate fields
are exported; failures preserve the last valid JSON. It does not export thread IDs,
account identifiers, authentication files or raw server responses.

## Verified scope and limits

`account/usage/read` is called with `{}` (no thread ID). On the first live probe on
2026-10-10, 150 records spanned 2026-04-08 through 2026-10-09. Their sum equaled the
returned lifetime total. Later same-day refreshes changed the latest daily total,
confirming that recent buckets may be incomplete and revised upstream. The saved JSON
contains its precise `syncedAt`, current totals and coverage; do not treat the initial
probe as the permanently current total.

The response does not specify the date timezone, input/output/cache composition,
product/device coverage, retention policy or freshness SLA. Dates are preserved exactly
as returned; only `syncedAt` is UTC. Missing dates are not filled with zero. In future,
lifetime summary and daily range may differ; `dailySumMatchesLifetime` records the
comparison. These metrics are not labeled as API billing or all ChatGPT usage.

## Integration and validation

See [INTEGRATIONS.md](INTEGRATIONS.md) for the endpoint contract, online hosting step,
and disabled visitor analytics configuration. GitHub Pages cannot itself run the
local authenticated updater. Production reads the independent HTTPS endpoint configured in `_config.yml`,
with the bundled snapshot as a fallback. Local preview uses the local API.
The cloud writer and scheduled-task authentication still require an end-to-end
verification in Your dot; publishing the endpoint does not enable a schedule.

Run tests with `python3 -m unittest discover -s scripts -p 'test_*.py'`. The Jekyll
preview has been built with Ruby 3.3 / Jekyll 3.10. Rebuild after source changes; JSON
updates made by the running preview server need no rebuild.

The Bio is preserved from the original master revision. Education is maintained in
`_data/education.yml`. Home-specific styling preserves other site layouts. The legacy
navigation bundle is excluded from the homepage because its hidden masthead caused
recursive navigation errors. Theme selection follows the system initially and saves
manual choices locally.

## Heatmap display

Unreported dates display 0.0M in the cell tooltip as requested. The stored JSON does not invent zero records, and the average still uses reported days only. Tooltips appear next to the focused, tapped or hovered cell.
