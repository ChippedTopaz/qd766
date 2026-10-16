# Operator recapture in the admin log hub

- Read existing staged-run checkpoints; do not enqueue, resume, modify or publish anything.
- Show today's staged runs in Tổng quan hôm nay and add Lịch sử khai thác → Nguồn: Hệ thống → Loại nhật ký: Cào lại theo yêu cầu.
- Show operation date, scoped province/period/group counts, completed/expected blocks, failures, changed score records and the explicit not-published state. A completed validated run is labelled Chờ duyệt thay thế, not deployed.
- Reuse the compact detail dialog and per-period phases, with ten block rows per page and success/running/issues filters. Existing daily/user request logs remain separate.
- Admin-only GET routes `/api/v1/admin/logs/recaptures` and `/api/v1/admin/logs/recaptures/{run_day}`. No new write route; no raw paths, archive metadata, credentials or source payloads returned.
- Enforce date inputs, fixed server root, no checkpoint/directory symlinks, 2 MiB/2,000-block bounds, at most 366 runs per search, and mtime/size cache of 64 runs. Stale RUNNING records become Cần kiểm tra rather than a false success.
- Active staged runs reuse the existing visible-today-only ten-second refresh. History/detail do not add polling.
- TypeScript, 11 backend tests and two UI test files PASS. Read-only projection of the live run took about 15 ms in the local check; no production database writes were performed by the reader.
- Source/build are prepared locally. Backend reload and frontend publication are still required before this UI appears on the production website.
