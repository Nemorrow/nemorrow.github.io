# Usage and visitor analytics

## Usage: repository snapshots

The homepage uses repository JSON and an embedded build-time snapshot. A local
macOS task updates both at 00:05 and 12:00 Asia/Shanghai, with login catch-up
and retries. Unchanged data does not produce a commit. `_config.yml` leaves
`token_usage.endpoint` empty. Independent storage and dot are no longer used.

See [TOKEN_USAGE.md](TOKEN_USAGE.md) for authentication, scheduling and failure behavior.

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
