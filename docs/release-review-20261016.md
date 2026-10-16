# Release review — 16 October 2026

## Subsequent approval and deployment checkpoint

The user approved the system-notices UI and authorized deployment after this review. Fresh backup `qd766-20261016-085833.dump` (105,379,093 bytes) verified SHA256 `A37D191472CB15AD16EFD779999C76F6B16219DAD46C6DEE1E4973F180197639`; archive TOC readable. Additive schema 20261016_0029 applied and notice model columns verified. No notice published. Backend Task Scheduler restart was denied to the agent; operator restart is required before frontend push. No worker restart or schedule change.

Status: reviewed locally; no commit, push, production restart or migration performed by this review.
Last published code baseline: 99a9a8a.

## Approved scope awaiting code deployment

- Daily chart 7/30/90-day shortcuts, shown only for a complete consecutive date window inside the selected period. One existing read request per selection, no collection or Credit mutation.
- Operator historical recapture in the admin log hub: today's progress, paginated history/detail, read-only bounded checkpoint projection, including the published state and archived-original confirmation.
- Presentation order shared by overview tiles, detail strip, rankings, time comparisons, agency comparisons and watch table: transparency, progress, online services, online payment, digitization, satisfaction. Only the dashboard presentation array is reordered; labels, payloads, formula configuration, values, ranks and score links remain unchanged.
- Preserve the existing collection-only maintenance gate. New requests remain paused by the local operator marker; no implicit reopening during deployment. History/entitlements, AI, collection worker and daily schedule are unaffected.
- Documentation records the national source's combined online-services display column. No group merging or formula change in this application.

## Already completed operationally, not a new deploy action

- Approved historical publication: 525 blocks, 510 detail snapshots + 15 national summaries.
- New daily generation starts at report date 15/10/2026, captured 16/10/2026.
- Old 06–15/10 daily links archived and excluded from active daily comparison; underlying old snapshots and database dumps preserved.
- Do not rerun publication or include raw recapture/archive files in the web package.

## Feature requiring explicit UI approval / release decision

System notices has backend, admin/user UI and tests, but no successful visual preview approval is recorded. It is currently wired into the local application. Do not push the whole dirty tree as an approved-only release without first approving this feature or separating its changes.

If included, backup then apply additive migration 20261016_0029, restart backend and verify protected endpoints before publishing the frontend. Production currently remains at schema 20261014_0028. Do not publish a real notice as part of deployment unless separately requested.

## Excluded

- Parallel workers, two-job runner, watchdog, queue limit five and their experiments.
- Per-TTHC version/refresh/credit policy changes.
- Source formula/group structure changes, existing saved formula edits, worker restart, schedule changes and automatic unpausing.
- Preview pages, mock APIs, temporary scripts, raw captures, archive dumps, credentials and source maps.
- Line-ending-only changes in worker.py, collection.css and types.ts.

## Verification during this review

- TypeScript build: PASS.
- 56 backend tests: PASS across collection maintenance, paid requests, user collection, recapture log, admin log hub, system notices, recrawl publication and staging guards. SQLite/in-memory only.
- 13 frontend test files: PASS for daily chart controls/model/UI, admin logs, notices, group display order, leaderboard, custom time comparison, agency comparison/watch, bento, exports and motion.
- Fresh isolated Netlify package + allowlist test: PASS; no fixtures/secrets/maps/preview pages.
- Whitespace diff check: PASS ignoring existing line-ending differences.
- Tests initially inherited the real operator pause marker; test setup now mocks only that gate locally. The actual production marker was not modified. Windows socketpair test initialization required loopback permission; rerun passed after granting it.
- Current production login/browser flow and visual approval are not established by these automated checks. No server load benchmark or live source collection was run in this review.

## Deployment sequence after scope approval

1. Explicit source allowlist; exclude experiments and temporary files; review staged diff.
2. Fresh code/database backup and archive checksum verification.
3. Only if notices approved: apply 0029; otherwise separate notices UI/router/model changes from this release.
4. Restart backend only if required for approved log/gate/notices code; preserve paused state. No worker restart.
5. Push approved frontend build, verify production version/assets, authentication protections, logs, chart shortcuts and score navigation.
6. Reopen user collections only upon separate user instruction.
