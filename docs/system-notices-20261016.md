# System notices — prepared for review

Release checkpoint: user approved the UI on 16/10/2026 and authorized deployment. Fresh database backup verified; migration 20261016_0029 applied. No real notice created/published. Backend restart and frontend publication remain pending at this checkpoint; historical review notes below describe the pre-approval state.

## Administration

- Sidebar entry Thông báo hệ thống, separate from source alerts and challenge notifications.
- Lazy-load a paginated library (10/page), filter drafts/published/archived, edit title, summary, plain multiline body and category (information, important, maintenance/update).
- Save a draft, open the same styled content renderer used for users, explicitly confirm publication. No browser alert/confirm dialogs.
- Published content is immutable. Stop automatic display to archive it; it remains in user history. Copy to a new draft for a correction/new announcement rather than rewriting history.
- All edits/actions require admitted admin + CSRF, use parameterized ORM queries and optimistic revision checks, and emit admin audit entries. Stable draft UUID prevents accidental duplicate creation on retry.

## User experience

- After an admitted user signs in and the dashboard renders, read notices once; no polling or per-render refetch.
- Open only the newest active notice, not a cascade of older popups. Dashboard remains usable if the optional notice endpoint is unavailable.
- Styled responsive dialog with category, publication date, title, summary and readable paragraphs; close/Escape/focus return and reduced-motion support.
- Đã hiểu closes the dialog for this page visit. Không hiển thị lại thông báo này persists a per-account/per-publication dismissal server-side, effective on other browsers/devices.
- Account menu entry Thông báo hệ thống opens the history (10/page), including dismissed and archived publications. Drafts are never returned to users.
- All content is escaped plain text; no arbitrary HTML, scripts, external media or links are rendered.

## Deployment boundary

- New additive Alembic revision `20261016_0029`, two notice-only tables; migration has not been run on production.
- No real notification created or published, no worker restart, Credit change, source observation import or schedule change.
- Static preview: `/system-notices-preview.html`. It uses an in-memory demo API and the real UI components, never production writes; excluded by the Netlify packaging allowlist.
- Preview must be started from the machine operator's terminal if the agent-hosted localhost server is inaccessible.
- TypeScript and backend/UI tests cover draft visibility, authorization, CSRF, conflict guards, server-side dismissal isolation/idempotency, pagination, archived history, no collection/Credit writes, and isolated migration upgrade/downgrade.
- Automated browser could not access localhost 8841 during this turn (timeout); visual approval remains pending.
