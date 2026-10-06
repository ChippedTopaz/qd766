# Daily capture schedule correction — 2026-10-06

Supersedes the previous 02:00 schedule. The operator reports that DVCQG refreshes
at 02:00, so collection must start at 04:00 Vietnam time to allow source refresh
to finish. Actual source completion is not guaranteed solely by the start time.

- Daily target boundary and scheduled trigger: 04:00 Asia/Ho_Chi_Minh.
- Preserve the reporting-date convention: capture on 07/10 reports 06/10.
- First eligible daily reporting date: 06/10/2026. Observations before this
  date are excluded from the history API and the annual overview comparison.
  Original observations/snapshots are retained for audit, not deleted/relabelled.
- Annual overview uses a native calendar input with min 2026-10-06 and max the
  latest available reporting date. Missing dates cannot be accepted. Until a
  valid observation exists, the calendar is disabled; no values are fabricated.
- Monthly/quarterly comparison menus retain their existing period logic.
- Daily freshness grace moves with the schedule: before 05:00, the previous
  capture boundary remains the freshness cutoff, allowing one hour to finish.

Existing installations: run tools/reschedule_daily_collection.ps1 -Confirm
from the repository. It verifies the expected daily task action, exports XML,
changes only the trigger and verifies 04:00. No database migration, worker
restart, collector invocation, principal/settings change or deletion is needed.
The new-install register_daily_collection_task.ps1 also uses 04:00.

Backend modules require the reviewed public-backend restart. Calendar frontend
requires deployment/reload; a source edit alone does not alter production UI.
Task Scheduler access from the agent was denied, so the operator must run the
reschedule command and send its verification output.
