# Live usage and visitor analytics

## Local live usage: implemented

Run `python3 scripts/serve_usage.py` from this checkout, or open the supplied
`Preview.command`. Python 3 is sufficient. The service binds only to 127.0.0.1:4173.

- `GET /api/token-usage` returns the sanitized snapshot with `Cache-Control: no-store`.
- A background worker refreshes it through the authenticated local App Server at
  startup and every hour while the service is running. `--refresh-seconds` can change
  this interval (minimum 300). This is not a persistent system task.
- The browser requests fresh data every five minutes while its tab is visible.
- API failure falls back to the saved JSON. Refresh failure keeps the last valid
  snapshot; the `syncedAt` field describes actual snapshot freshness.
- No account credentials, thread data or authentication files are served. Only the
  built `_site` directory and the aggregate API are reachable.
- To inspect offline, add `--no-sync`; no account request is then made.
- Upstream data may lag or omit days. Polling does not change that reporting scope.

## Independent production storage

Production reads https://shiye-token-usage.upbeatpeach9.chatgpt.site/api/token-usage.
The browser checks every five minutes while visible and falls back to bundled JSON.
This public, CORS-enabled endpoint serves only aggregate daily counts. Its independent
R2 storage can be updated without commits or deployment of this homepage.
Before the first authenticated upload, it serves the verified initial snapshot.

The Sites MCP plugin exposes `read_token_usage` and owner-only `update_token_usage`.
Writes require the platform-authenticated owner identity; no account credential is
stored in this repository or sent to visitors. Uploads validate dates and integers,
reject older snapshots, and skip unchanged data. Failed updates preserve existing data.

Your dot has verified account usage and login persistence after restarting App Server
in the same cloud configuration. Persistence across scheduled tasks, the first
owner-authenticated storage write and a scheduled execution remain to be verified.
No automatic schedule is enabled by this repository.

Response contract: `schemaVersion: 1`, UTC `syncedAt`,
`days: [{date: "YYYY-MM-DD", tokens: integer}]` and optional lifetime summary.
The service derives coverage and totals. Dates retain the source's unspecified timezone.
Missing dates display `0.0M` beside the cell without adding synthetic records or
changing the reported-day denominator of the average.

## Visitor analytics: prepared, disabled

The homepage has an optional Umami tracker. Create a site in Umami Cloud or your own
Umami deployment, then copy its script URL and website ID into `_config.yml`:

```yaml
visitor_analytics:
  enabled: true
  script_url: "https://YOUR-ANALYTICS-HOST/script.js"
  website_id: "YOUR-PUBLIC-WEBSITE-ID"
  domains: "shiyelei.com,nemorrow.github.io"
```

Use the actual domains serving the homepage. These are public tracker settings;
never put an analytics API key or account password in this file. The script is only
included for `JEKYLL_ENV=production`, with domain filtering, Do Not Track support,
and query/hash exclusion. Local previews do not collect visits.

After an authorized production deployment, the private analytics dashboard can show
daily visitors, pageviews, referring websites, and approximate countries/regions.
Filter the page path to `/` to inspect homepage visits. These are measured estimates,
not an exact count of identifiable people; blocking, shared devices, VPNs and absent
referrers limit completeness. It cannot reconstruct visits from before collection
begins. No dashboard data has been fabricated and collection is not currently active.

Official documentation:
- https://docs.umami.is/docs/collect-data
- https://docs.umami.is/docs/tracker-configuration
- https://docs.umami.is/docs/metric-definitions
