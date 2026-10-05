# Local comparison redesign and read-only collection audit

## UI

- Sidebar: So sánh theo thời gian / So sánh theo cơ quan.
- Delivery warnings on both screens are retained under a closed-by-default Lưu ý disclosure.
- Agency comparison starts with the ranking table. Distribution, neighboring units and similar-volume cards are removed.
- Sở/ngành and xã/phường are separate cohorts; six score columns, total, point change and rank change.
- All groups contribute to the unit inventory, including units absent from the first dataset.
- Total requires six finite source scores and maxima. Missing is not zero.
- Exact previous same-type period and same scope/TTHC only. Rank changes additionally require an identical fully scored cohort.
- The permission allowlist restricts both table and Excel. Agency-only users do not receive a fabricated province-wide rank from a one-unit cohort.
- Searching keeps focus. Sorting does not truncate to 60 units. Sticky headers and unit names support mobile horizontal scrolling.
- Unit and group links keep period/province/scope and open the corresponding Overview tab.
- Excel reads the visible, filtered table, preserving the same fields and signed point/rank changes.
- Static preview synced; no production restart, scheduled task mutation, Git push or Netlify deploy.

## Actual PostgreSQL inventory

Audited 2026-10-05T06:26:08.680416+00:00, enforced REPEATABLE READ / SET TRANSACTION READ ONLY.
Command: project Python, tools/audit_data_coverage.py --summary.

| Period | Province details with 6 groups | Sở/ngành with 6 scores | Xã/phường with 6 scores | National capture time (Vietnam, 5 October) |
| --- | --- | --- | --- | --- |
| month-2026-01 | 34/34 | 517 | 3321 | 08:25:51 |
| month-2026-02 | 34/34 | 517 | 3321 | 08:25:52 |
| month-2026-03 | 34/34 | 517 | 3321 | 08:25:52 |
| month-2026-04 | 34/34 | 517 | 3321 | 08:25:53 |
| month-2026-05 | 34/34 | 517 | 3321 | 08:25:53 |
| month-2026-06 | 34/34 | 517 | 3321 | 08:25:53 |
| month-2026-07 | 34/34 | 517 | 3321 | 08:25:54 |
| month-2026-08 | 34/34 | 517 | 3321 | 07:21:48 |
| month-2026-09 | 34/34 | 517 | 3321 | 07:46:12 |
| month-2026-10 | 34/34 | 517 | 3321 | 07:46:12 |
| quarter-2026-01 | 34/34 | 517 | 3321 | 08:25:54 |
| quarter-2026-02 | 34/34 | 517 | 3321 | 08:25:55 |
| quarter-2026-03 | 34/34 | 517 | 3321 | 07:46:13 |
| quarter-2026-04 | 34/34 | 517 | 3321 | 07:46:13 |
| year-2026 | 34/34 | 517 | 3321 | 07:46:13 |

510 province-period snapshots; 15 validated national summaries. Across each period,
3,838 child units are returned by the source, 23,028 child group-score rows.
There are 345,420 child group-score rows across these 15 periods.
No recorded scored child unit is missing one of the six groups.
This measures the source-returned inventory, not proof that an independent directory
of every legally established agency is complete. No 2025 yearly history was found;
do not fabricate a previous-year comparison.

Historical checkpoint: 349 SUCCESS / 1 FAILED (national month 8, ConnectTimeout).
An existing valid month-8 national summary was captured at 07:21:48; the latest
backfill did not replace it. Month-8 agency details were saved 08:25–08:28.
Current month/Q4/year national summaries: approximately 07:46; their two-hour
freshness flags are true at audit time, despite being captured on the same day.
Latest agency details cover 07:19–08:57 today. Phú Thọ Sở Văn hóa,
Thể thao và Du lịch month 9 now sums to 72.20 instead of the old 70.45.

## Scheduling is NOT verified/active under the new policy

Task Scheduler inventory is unavailable to this agent (access denied; alternative
read-only schtasks queries failed). A read-only PowerShell inventory was requested
from the operator. Registration code alone is not proof of active task scheduling.

Legacy registration source: national summaries hourly, province detail scheduler
02:15 daily with the old 72-hour staggered selection, database backup 01:30.
The newly prepared daily/finalization policy is not yet wired to those tasks.

Database control is OPEN / operator-requested-pause, lease empty; 15 jobs queued.
Legacy batch states still queued/running even though independent controlled
collection has saved the data. Do not silently unpause/re-run these stale batches.
Daily scheduler dry-run today returns no due periods, because current-day
observations exist; it also reports the open control. This is not a health PASS.

Required next release step: inspect actual task actions/triggers; reconcile obsolete
legacy batches against the verified observations; explicitly review resuming
collection; then wire the reviewed daily policy and controlled worker to tasks.
Daily baseline is current month, quarter and year across 34 provinces:
102 detail blocks × 6 groups = 612 detail requests plus 3 national summaries,
excluding retries/catalog calls and one-time missing/finalization work.
Closed periods stay unchanged after one post-close capture unless the operator
requests refresh for a source revision.

## Checks

TypeScript build; agency model and actual renderer tests; summary-only renderer;
comparison Excel, branding and loader tests pass. Six Python coverage/daily-policy
tests pass. Browser visual acceptance remains with the operator.
