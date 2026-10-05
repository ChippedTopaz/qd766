# Local acceptance: daily refresh, pooled TTHC collection, admin monitor

No Netlify push/deploy, scheduled task registration or production worker
replacement is performed by this change. Current source tree contains earlier
unreleased Excel work; do not deploy the whole tree without reviewing that scope.

## Policy prepared for acceptance

- Current month, current quarter and current year are due on each Vietnam-local
  calendar day, not staggered 72-hour rotation.
- Closed month/quarter/year needs one verified capture at/after the next period
  starts. A snapshot from before closure is not final. Already observed closed
  periods are not crawled daily. Source revisions can still require an explicit
  administrative refresh, not automatic repeated historical collection.
- `schedule_daily_refresh.py` defaults to a read-only plan. `--confirm` creates
  versioned province batches only under a closed circuit, with no other pending
  batches. The national collector supports `--daily-policy --dry-run` and the
  same due-period rules. Neither new policy is wired into Windows tasks yet.
- Historical province-periods absent for some of 34 roots appear as one-off
  missing/finalization backlog. A completed aggregate is not proof of complete
  agency details. Do not silently mark that backlog finished.

## Worker prepared for acceptance

`run_collection_worker.py --controlled` explicitly selects a pooled HTTP client
and three concurrent group requests inside each job. Job claiming remains one
coordinator/shared lease, so the global limit is not multiplied by worker count.
Request priority 50 remains ahead of background priority 55. No Credit logic or
shared-job entitlement logic changes. Unsupported satisfaction-by-TTHC remains
omitted (five supported groups), not replaced with invented values.

Transient retries are 1/2/4/8 seconds; successful groups are retained on retry.
Rejection/authentication/rate-limit signals still stop for review. A new actual
controlled job uses an immutable observation ID, allowing identical content to
have a fresh collection record without altering old dates/content. Re-import of
the same observation remains idempotent. Old scheduled worker is unchanged.

## Local admin test

1. Reload the Google trial backend on 8771 with the existing verified restart
   script (run in the user's PowerShell if agent lacks process inventory access).
2. Open `/admin.html`, log in as the trial admin, select **Nhật ký khai thác**.
3. Filter default/TTHC and job states, exercise pagination and refresh. Only GET
   requests exist; no cancel/resume/circuit/credit control is exposed here.
4. Local jobs are labelled simulation. The completed real-data pilot is shown
   separately from the server-configured read-only SQLite checkpoint: 170 detail
   blocks and 5 national summaries, 965.32 seconds, no failed blocks.
5. Normal/national-view users cannot read this API; unauthorized gets 401, non-admin
   gets 403. Invalid filter/injection strings get 422. POST has no handler.

Front-end backup: `.tmp-release-preflight/admin-daily-20261005-backup/`.
The local preview static files are synced in `.tmp-credit-trial/site`; production
services and Netlify are not refreshed.

Verification: 242 Python tests, TypeScript build, admin monitor render/XSS smoke
test pass. Covers local midnight/year rollover, post-close finalization, pool
limits, checkpoint/hash resume, five-group TTHC processor, new immutable
observation IDs, admin authorization, read-only API and invalid filters.
