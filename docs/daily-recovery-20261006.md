# Recovery of reporting day 2026-10-06

## Cause

The six failed blocks were Quang Ninh and Hue, each for year 2026, month
10/2026 and quarter 4/2026. All six group responses had already been captured.
The import validator rejected differing agency inventories between source
endpoints with `ValueError: Agency list differs across groups`.
HTTP retries therefore could not resolve this deterministic validation error.

## Recovery performed on 2026-10-07

- PostgreSQL backup before changes:
  `.tmp-daily-recovery-backups/qd766-20261007-143108.dump`.
- SHA256: `92D206FA82E1D41221A0DE5C54FCBFAC804F4AC07B0E823F76446168352A19FF`.
- Reused the retained original group captures, timestamped 04:02–04:09 on
  2026-10-07 (Vietnam), under `data/daily-collection/2026-10-06/captures`.
- Ran the resumable collector with `--execute --expected-report-date 2026-10-06`.
  The date argument is a guard, not an override of the reporting policy.
- Existing 96 observations were skipped; only six missing blocks were imported.
- Read-only PostgreSQL verification: 102 observations for 2026-10-06,
  comprising 34 provinces for each of the three periods. All six repaired
  snapshots have six datasets and retain original capture timestamps.
- Read-only admin checkpoint verification: COMPLETE, 102/102, no failed blocks.

## Source omissions are not fabricated

Quang Ninh has 71 agencies across the union of the six source inventories,
of which 68 appear in every group. Hue has 55 in the union and 54 in every
group. Every available source row is retained. Missing group rows are recorded
in `dailyAgencyCoverage.missingByGroup`, not generated as zero-score rows.
Daily agency total/ranking still requires six actual scores.

## Retry and unchanged safeguards

Transient failed-group collection is attempted up to three times per block,
with 1- and 2-second pauses. The existing per-request retry limit remains four
retries. Successful immutable group captures are reused instead of re-fetched.
Safety stops (including source access/rate-limit signals) are not bypassed;
invalid normalized data is not blindly retried or imported.
The shared collection lease, 04:00 reporting boundary, credits, paid requests,
AI settings, and actual Windows task configuration were not changed.
The stale admin schedule label was corrected from 02:00 to 04:00 in frontend
source and compiled assets; publishing that label requires the next frontend
deployment.

## Verification

334 backend tests passed; TypeScript no-emit check and admin collection render
test passed. Tests cover bounded retries, successful checkpoint reuse,
safety-stop/invalid-data behavior, date guard, and mismatched source inventories.
