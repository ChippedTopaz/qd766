# Daily indicator combo chart and saved-day calendar — local draft

Status at initial review: implemented/tested locally, not staged/committed/pushed. On 14/10/2026 the owner approved frontend deployment of this chart/calendar update together with registration hardening, source-monitor UI and whole-indicator-row selection. See release-20261014.md for scope and validation. The owner has already restarted the protected backend for the saved-day `preceding` response; no worker restart is required.

## Display and data

- Existing chart was bespoke HTML/SVG, not a chart-library instance. New SVG combo component exposes `dailyComboOptions`; no external dependency/CDN added.
- Left Y axis: current day's achieved count minus the literal previous calendar day's achieved count. Light-blue bars (`#3b82f6`, opacity 40%). Axis starts at 0, with integer steps and four intervals/five gridlines exactly shared with the right axis. Negative cumulative corrections retain their true value in the table/model/tooltip and get a small downward marker at zero, not a negative bar or a fabricated zero. Missing count/day/prior produces no invented bar. First day uses the separately provided immediately preceding saved day, never a previous arbitrary available date. Mock increments use Math.round() and contain no negative counts.
- Right Y axis: absolute indicator ratio on a fixed 0–100% scale, orange monotone cubic curve with markers. No overshooting/interpolation over missing observations. If no ratio exists anywhere in the interval but source/display score exists, use a score line, its own maximum and `Điểm số` tooltip label; never mix ratio and score in one line. No change to existing scoring projection/formulas.
- X axis retains every day inclusively between the two selected dates. Tick labels alone are skipped according to actual pixel width (ResizeObserver, minimum 62 px label spacing); resizing does not fetch data. Hover/tap/left-right/Home/End expose one shared tooltip: full dd/mm/yyyy date, signed daily delta, ratio percent (or explicitly labelled score). Escape/blur/pointerleave dismiss it.
- Two saved-day calendar popovers replace long date dropdowns, retaining dd/mm/yyyy. Quick month/year selection and previous/next eligible months. Only stored available days of the current API context can be selected; baseline < evaluation, unavailable/same/reversed days disabled. Escape, outside click and focus-out dismiss. Missing default preceding day still shows the date and existing warning; no silent fallback.
- Table layout, endpoint totals/deltas, indicator selection, own-unit scope and all-TTHC-only policy unchanged. Chart/date widgets clean observers/global listeners on context changes. Rerenders retain the existing cached HTML projection.
- Footer label is `Biến động`. Numeric table headers/cells, value pairs and deltas explicitly align right using tabular numerals, without changing other tables or mobile label placement.

## Backend/performance/security

- Same authorized GET returns `preceding` with at most one extra day's entity (same root/unit/group/period, complete snapshot, dates >= existing 06/10 valid-history cutoff). Batched with intermediate-day query; zero collection jobs/Credit writes/provider requests. Frontend validates context/preceding date/period before use.
- Province intermediate/preceding group-score provenance follows the linked national-summary policy already used by endpoint days; constant batch queries, not per-day lookups. Never returns another province's summary or peer details.
- Existing bounded backend cache and frontend HTML cache retained. No schema/migration, auth/account, billing/Credit, worker/watchdog, schedule or formula-configuration changes.
- 44 backend tests PASS (daily indicators/selection, public registration/security boundaries). TypeScript PASS. Ten frontend test files plus province actual-app profile PASS, including direct chart/calendar DOM adapter tests, 7/30/90/366 date intervals, negative/zero/missing values, smooth segments, safe tooltip formats, responsive tick spacing and cleanup.
- SQLite: 100 warm GETs p95 6.77 ms / 4 SQL incl auth; cold 46.10 ms / 13 SQL. Seven-day range 15 SQL / 5,737 bytes, 0 writes. These are isolated tests, not a production load estimate.
- Initial-draft SVG string rendering only (before the four UI refinements, no browser DOM/layout measurement), 50 iterations: p95 7/30/90/366 days 0.72/0.59/0.56/1.32 ms. Initial two modules gzip total 5,993 bytes. No polling/per-day HTTP/interaction requests.
- Initial-draft public package `.tmp-combo-package-20261014-0851/netlify-public` passed allowlist verification; previews/fixture JSON/source maps excluded. This package predates the four UI refinements and must be rebuilt before deployment. Launcher config/schema check is read-only.

## Visual preview limitation

Computer-use skill attempted through the preferred browser connector; initialization failed with `failed to write kernel assets` (Windows error 3). Agent-started preview server could not be reached over loopback and was stopped through its own exec session; no other server/process touched. Do not claim screenshot/multi-device browser QA or a currently live preview link.

Manual local preview (keep terminal open):

```powershell
.\.venv\Scripts\python.exe -X utf8 -u .tmp-daily-indicator-preview.py --port 8838
```

Then http://127.0.0.1:8838/daily-combo-preview.html exercises synthetic 7/30/90-day ranges, including a missing date. The 366-day preview option was removed at the user's request; annual-period safety remains covered by automated tests, without limiting real date selection. Negative corrections are covered separately by automated tests, not generated as mock workloads. Root URL exposes the integrated app fixture. Preview files remain outside release allowlist/public package. Real data does not start before 06/10; long-range demo dates are deliberately synthetic.

Before eventual approved deployment: public backend restart required for `preceding`; frontend remains backward-compatible with earlier bodies lacking it (first bar explicitly missing). Push only when approved/readiness verified. No worker restart required.
