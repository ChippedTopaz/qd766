# Controlled refresh pilot — 5 October 2026

Authorized scope: all-procedure data for all 34 provinces and their child agencies,
September and October 2026, quarters III and IV, and year 2026. Quarters I/II and
older months are not part of this pilot.

The original 15-period queue remains operator-paused. Do not close its circuit:
that would resume the earlier full-year sequential queue as well. The isolated
runner reserves the shared lease without opening the legacy queue for execution.
It refuses to run through an upstream rejection or safety stop.

## Architecture

- Shared HTTP connection pool, three concurrent group requests, globally spaced
  starts by 0.4 seconds; 2.5 seconds between province blocks.
- Four exponential retries for transient transport/5xx errors. Permanent group
  failure retains successful checkpoints, skips publishing that province-period,
  and continues independent blocks. Authentication/rate-limit/WAF rejection stops
  the isolated run for review; no identity rotation or bypass.
- Per-group manifest with validated root/schema, hashes and atomic checkpoint.
  Fetch declared pagination and retain individual pages before assembling groups.
- Single-thread coordinator writes manifests; SQLite commits block status after
  each result. A complete six-group capture is normalized and transactionally
  imported by the existing importer. Existing snapshots and Credit are untouched.
- Content-addressed deduplication remains: unchanged content can reuse an older
  snapshot ID. The checkpoint records fresh validation time; displayed capture
  time may still be old for unchanged snapshots. This needs separate freshness
  metadata work, not replacement of historical dates.

## Run/status

From the project directory:

```powershell
.\.venv\Scripts\python.exe .\tools\run_controlled_default_refresh.py
.\.venv\Scripts\python.exe .\tools\run_controlled_default_refresh.py --execute
.\.venv\Scripts\python.exe .\tools\check_controlled_refresh.py
```

Same run ID resumes successful SQLite blocks and validated per-group captures;
it refuses a live/stale owned lease until the operator has reviewed recovery.
Do not run a second collector or reset leases while a process is active.

Artifacts: `.tmp-release-preflight/controlled-20261005/`; live stdout/stderr in
`runner.out.log` / `runner.err.log`. Expected final success: 170 province-period
blocks plus five national summaries. Partial failure must not be called complete.

No worker task deployment, backend restart, Netlify deployment or fee changes
are part of this pilot. The reusable collector is in `qd766.concurrent_collection`;
the old deployed scheduled worker has not been replaced.
