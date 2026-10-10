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

Production `token_usage.endpoint` is intentionally empty; local preview overrides it
with `/api/token-usage`. Existing frontend behavior therefore remains valid on GitHub
Pages, falling back to the bundled snapshot.

## Online automatic updates: a hosting step remains

GitHub Pages is static hosting and cannot run the authenticated updater:
https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages

To update the public homepage without pushing the website each time, host only the
sanitized JSON on an HTTPS endpoint and configure `token_usage.endpoint` to that URL.
The local updater must then upload that JSON to the chosen storage/API on its own
schedule. A cross-origin endpoint must allow the homepage origin via CORS. Keep
publication credentials outside the repository and never expose App Server itself.
No remote endpoint, upload job, system service, push or deployment has been created.
That requires choosing the hosting destination and explicitly enabling publication.

Response contract: the existing `assets/data/codex-usage.json` schema, including
`schemaVersion: 1`, `syncedAt`, and `days: [{date: "YYYY-MM-DD", tokens: integer}]`.
Numbers remain exact integers in the data; the daily tooltip rounds to one decimal
million, e.g. `114.4M`. An absent day stays “No record returned”.

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
