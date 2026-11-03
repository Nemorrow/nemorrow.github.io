# Hourly cloud usage synchronization

The hourly job uses the published GitHub snapshots as its durable data baseline. A cloud worker can start from an older filesystem without having to reconstruct a local run history. Each invocation loads reviewed source from a fixed repository commit into a fresh temporary directory; credentials stay in the existing authorized App Server configuration.

This protocol replaces the retired local run-ledger protocol. Keep old state, locks and evidence for inspection; do not initialize, replay, clear or rewrite them. Before activating the new protocol, verify that no old sync invocation can still publish. Update the existing schedule in place.

## Source collection

Load `cloud_usage_sync.py` and `sync_codex_usage.py` from the configured immutable commit, verify their recorded SHA-256 hashes, and execute them only from a fresh run directory. Use the pre-existing isolated `CODEX_HOME`, its expected marker and the configured authorized account. Missing or mismatched identity, marker or permissions stops the run. Do not copy, inspect or upload authentication files, start a login, or create a replacement home.

`collect` checks `account/read` and the Pro plan in the same App Server session before calling `account/usage/read`. Only aggregate daily counts and a redacted receipt are written. The candidate timestamp records the start of the usage request, rather than when a delayed request completes. Dates must be unique and counts must be nonnegative safe integers; their sum must equal the reported lifetime total. Missing days remain missing. The source does not establish a date timezone or an update-time guarantee.

## Comparison and conditional publishing

1. Read the current `master` ref and its commit/tree. Read both snapshots at that exact SHA:
   - `assets/data/codex-usage.json`
   - `_data/token_usage_snapshot.json`
2. Run `plan` against those snapshots and the fresh candidate. Compare `schemaVersion`, `days` and `summary`; a changed timestamp alone is not a data change. `unchanged` invokes no GitHub write tools and no Pages polling.
3. A candidate older than a published snapshot must not overwrite it. Discard a stale candidate before any retry and collect again if needed. A candidate expires after ten minutes. An equal timestamp with different statistics is ambiguous and stops the run. Official totals may be revised downward; monotonic growth is not an API contract.
4. Before each GitHub write, check candidate age and re-read the branch. If the head changed, read both snapshots at the new head and plan again. Discard any tree or commit prepared from the previous head and rebuild from the new base tree; changing only its parent can overwrite concurrent frontend work. Never merely rebase an old candidate after a conflict.
5. For `change`, create one tree based on the just-read tree, with exactly the two snapshot entries containing the same complete candidate JSON. Create one commit whose sole parent is that head. Update `master` with `expected_sha=head` and `force=false`. The matching parent and non-forced ref update reject a competing sibling commit. Do not use separate Contents API commits or force pushes.
6. When a write response is uncertain, inspect the current head and its data before retrying. If both snapshots already contain the intended statistics, ignore a timestamp-only difference and do not create another commit. Validate the corresponding Pages deployment and make a real public JSON GET. A deployment still in progress is pending verification, not a reason to publish again. If a pending commit has been superseded, reconcile the current head and ancestry; never re-push its old snapshot.

The timestamp check orders candidates relative to *published* snapshots, not every unpublished observation of the source. The workflow is idempotent for the published content; it does not claim exactly-once execution, a cross-tool atomic transaction, or that the source is current to today.

## Recovery, retries and notifications

Keep task protocol version, immutable source commit/hashes, last outcome, source read time/date, pending deployment SHA and redacted failure/notification metadata in the existing platform schedule. These records help recovery and notification deduplication; they are not a local filesystem prerequisite for reading the source. Read GitHub as the data authority every time. A pending SHA must be reconciled with the current branch before a new publish.

Only explicit network timeouts, HTTP 429 and 5xx failures receive up to two additional attempts, after 15 and 45 seconds, respecting a longer Retry-After. Authentication, identity, marker, schema and permission errors stop and notify. Unknown RPC failures are not automatically treated as retryable. Re-check the branch and candidate on every write retry; never repeat an uncertain write blindly.

Ordinary unchanged runs stay quiet. Notify on a meaningful failure, required user action, or once when a genuine scheduled run confirms recovery. Preserve failure phase and actual time; manual tests never count as scheduled success. A new filesystem generation is not itself a failure if trusted source can be reloaded and the original identity verified. A missing or invalid original identity remains a real blocker.

The first scheduled invocation after activation must prove that it fetched the configured source, verified the original account, collected fresh usage and completed comparison/publishing. Saving a schedule, offline tests or a manual run cannot substitute for that evidence.
