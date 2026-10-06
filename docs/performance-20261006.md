# Dashboard compact transport — 2026-10-06

Local implementation, not yet verified as deployed to production.

The full dashboard loaded detailed metrics/parameters for every historical
period before displaying the initial period. Compact transport retains all
periods, units, authoritative scores and totalReceived for historical
comparisons, but loads detailed metrics only for the initial period. Selecting
another period fetches existing data through GET /dashboard/selection; it does
not enqueue collection or consume Credit. Legacy/export callers retain full
payloads unless compact=true is explicit.

The frontend also indexes entities once per group while calculating unit totals
and retains at most two recently opened provinces for 30 seconds in page memory.
No account data is persisted in localStorage/sessionStorage by this cache.
Server-side agency filtering still runs before fast response serialization.

Read-only Phu Tho measurement (15 periods, 164 units), construction plus JSON:

| Mode | Seconds | JSON MiB | gzip MiB | Detailed periods |
|---|---:|---:|---:|---:|
| Full | 1.939 | 13.251 | 1.090 | 15 |
| Compact | 1.283 | 4.615 | 0.561 | 1 |

These are backend measurements, not end-to-end browser latency. Production
network, rendering and runtime still need verification after rollout.

Validation: 267 Python tests pass, TypeScript compiles, analytics/history,
annual overview, agency comparison, summary-only, collection/reuse, restored
historical detail and bounded-cache tests pass. Restored detail is GET-only.

Restart the reviewed local Google trial to load new backend modules. Syncing
static assets alone does not refresh an already-running Python server. Do not
restart production or push Netlify as part of local verification. Do not stage
raw daily-collection files, database backups or temporary diagnostic scripts.
