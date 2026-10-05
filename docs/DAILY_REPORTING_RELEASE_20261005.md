# Daily reporting release — 2026-10-05

## Reporting contract

The governing business policy is [DATA_COMPARISON_POLICY.md](DATA_COMPARISON_POLICY.md): daily observations are advisory; official comparisons/statistics/reports require completed periods and compatible calculation bases. Formula changes must not be treated as ordinary daily performance changes.

- The 02:00 Vietnam capture on 06 October is labelled report date 05 October. Actual collection times remain separately visible. This is a reporting convention, not a claim that DVCQG has finalized data at midnight.
- Three periods containing the report date are collected: month, quarter, year. On the first morning of a new period the previous period is finalized; subsequent mornings refresh the new period.
- 34 provinces × 3 periods = 102 detail blocks, six groups each, plus three national summaries. Child agencies are included in every detail block and their identities must match across six groups.
- Identical daily values are still separate immutable daily observations. Existing undated snapshots are not retroactively assigned reporting dates. Missing prior days show no change, never invented zeros.
- A late startup captures the latest due report date and records its actual timestamp. Missed older days remain gaps; they cannot be reconstructed from current source data.
- Three HTTP requests maximum, shared collector lease, 0.4-second pacing and 2.5-second inter-block pause. Transient errors retry; failed blocks remain resumable. Source rejection/auth/rate limits and operator pause retain safety stop.
- Per-block PostgreSQL observation plus SQLite checkpoint; completed blocks do not recrawl. User TTHC requests retain independent Credit accounting and shared-job logic.

## Verified baseline (2026-10-05)

15 reporting periods: months 1–10, quarters 1–4, year 2026. All 34 province snapshots have six groups in each period. Each period includes 517 departments and 3,321 communes/wards returned by the source (3,838 children); this is not an independent legal directory audit. National summaries have 34 provinces and six groups. No annual 2025 history is available. Previously captured closed periods may still be revised by the source and require an explicit refresh if discrepancies arise.

## Deployment status

PostgreSQL additive migration 0017 was applied after verified backup `.tmp-daily-db-backups/qd766-20261005-140455.dump` (SHA256 `0079957B266104C294101F539483699E358972BAAC040071082676B95C247681`). Upgrade also included pending additive registration migration 0016. No existing score/Credit records were removed.

Windows task activation is NOT performed by the agent: Task Scheduler/process inventory access is denied. Existing services have not been stopped. No Netlify push/deploy has occurred.

Run from the project in the operator's PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\register_daily_collection_task.ps1 -Confirm -Backup ".tmp-daily-db-backups\qd766-20261005-140455.dump" -AllowInteractive
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\restart_public_backend.ps1
Get-ScheduledTask -TaskName "QD766 Daily Collection" | Get-ScheduledTaskInfo | Select-Object LastRunTime,LastTaskResult,NextRunTime
```

Interactive mode requires the Windows account to remain logged in and the machine awake. For logged-off execution use `-Credential (Get-Credential)` instead of `-AllowInteractive`; do not send passwords in chat. If backup is older than 24 hours make a new backup and supply its path.

Installer backs up task XML, disables the two old refresh schedules, retargets the existing worker to controlled collection, reconciles only independently verified completed default batches, and reopens only the explicit operator pause. It refuses unexpected process identity or paid-job involvement. Other safety pauses are not bypassed. The daily task is not manually started by the installer. If installation fails, retain the pause and inspect saved XML before restoring schedules; do not enable both collectors.

Daily collection log: `.tmp-runtime-logs/daily.log`; controlled worker log: `.tmp-runtime-logs/controlled-worker.log`. Admin collection log shows reporting date, status, completed blocks and errors. User comparison provides daily history and same-cohort rank changes. First genuine daily change requires two consecutive daily observations.

## Verification

255 Python tests passed; daily isolated runner additionally passed injected failure, continuation, resume and no repeat HTTP capture tests. TypeScript build and daily history, agency comparison and admin collection rendering tests passed. PowerShell task/launcher syntax parsed successfully. Actual unattended task execution and source completion remain operator acceptance checks, not simulated test results.
