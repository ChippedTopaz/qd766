# Dark mode feasibility

## Current scope

Sidebar collapse was cancelled by the user and removed. Long agency/province names wrap in their existing table cells without truncation. Dark mode remains analysis only; no theme change is enabled.

## Evidence from the current frontend

- `web/styles.css` already defines semantic colors (`--bg`, `--surface`, `--ink`, `--muted`, `--line`, positive/negative colors), but also contains hard-coded white surfaces.
- `web/bento.css` and `web/admin.css` use many direct hex colors for cards, text, borders and statuses. Changing the page background alone would leave white cards or unreadable labels.
- Account and Credit dialogs inject their own inline colors/styles. Tom Select dropdowns, SVG/chart axes, gauge tracks and loading/login states require explicit theme coverage.
- Score grades and favorable/unfavorable changes are business semantics: red/orange/yellow/light green/dark green and positive-green/negative-red. A theme must not reverse these meanings.

## Recommended implementation

1. Centralize semantic color tokens shared by both apps: canvas, card, raised surface, text, secondary text, border, hover, focus and status foreground/background. Preserve group identity and grade semantics while adapting contrast.
2. Provide Light / Dark / System choices in the account menu, store only the display preference locally, and apply the resolved theme before page paint to avoid a white flash. No account, Credit, permission or collection changes.
3. Cover main dashboard, Admin, login/loading, native and custom dialogs, tables, Tom Select, calendar controls, all graph labels/tooltips and account popovers. Keep the CCHC logo on white backing.
4. Keep print and exported Excel/report styling light. Theme affects screen display only, not data or export values.
5. Verify readability, focus, positive/negative status meaning and all five grades on desktop/mobile. Test system-theme changes, blocked storage, and initial paint.

## Assessment

Feasible without backend/database changes. A CSS-token theme and small local preference handler should have negligible runtime overhead; no additional data requests are necessary. Main cost is visual QA across existing views, not server performance. Treat as a separate UI release after the current performance/layout fixes are accepted; do not use a global color-inversion filter.
