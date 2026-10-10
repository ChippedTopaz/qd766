# Public registration — reviewed implementation

## Flow

The registration entry verifies Google identity first, then collects full name, birth date, gender (male/female), optional workplace, province and agency. Public self-registration only permits agency accounts. Province accounts remain administrator-issued through the invitation workflow. Name starts blank; every field except workplace is mandatory, including acceptance of the declaration of accuracy.

UI revision: primary action is “Đăng nhập với Google”. Registration is a small text line “Chưa phải thành viên? Đăng ký ngay!”, not a second button. The form displays verified Google email as read-only and omits the introductory approval/trial paragraph. “Đăng nhập nếu đã là thành viên” ends the application session via CSRF-protected logout, then opens ordinary Google sign-in (without registration intent). Only already admitted accounts enter the dashboard; pending applications are still blocked. These wording changes do not bypass approval.

Applications remain pending and cannot access dashboard data until an administrator approves them. Existing invitation links remain supported and agency-only. Approval uses the existing one-time invited-trial grant: one calendar month and 100 Credit starting at approval, never submission. Repeated approval does not grant again. Existing admitted accounts do not gain another trial by opening registration.

## Security and data

OAuth intent is stored in the server-side login attempt, not trusted from callback parameters. Existing state/binding/PKCE checks remain. Mutating requests require a current Google-authenticated session and CSRF. Public account tier is restricted server-side to agency; province, national, administrative and cross-province assignments are rejected. Submitted profile values are validated and escaped in the admin UI. Birth date, gender and workplace are returned only to administrators, not public rankings. Existing scope enforcement remains.

Public registration follows the existing shared-registration feature flag. Review still requires administrative role and source wallet availability. No passwords or new external mail service are introduced. No approval email is promised; users can check status or sign in again.

## Verification

- TypeScript compilation: PASS.
- Backend: 421 tests PASS, including public registration and schema compatibility checks.
- Frontend: 70 test files and production package test PASS.
- Earlier browser review used isolated SQLite and simulated Google login, not real production OAuth.
- Live PostgreSQL upgrade 0024 to 0025 completed after a verified backup; saved formulas unchanged.
- Real Google OAuth and production UI still require post-restart smoke verification.

## Deployment prerequisites

See `release-20261010.md` for the release checkpoint. Schema is now `20261009_0025`; restart backend and confirm readiness/runtime policy before publishing matching frontend. Existing saved formulas are neither changed nor reseeded. Migration defaults old applications to agency tier and does not delete existing records. Downgrade intentionally refuses to discard new profile data; any database restoration requires a separate reviewed recovery plan.

## Preview

Loopback preview: `http://127.0.0.1:8822/preview/login`; mock review: `http://127.0.0.1:8822/preview/admin`. Simulated Google, isolated SQLite, no real Credit or production user edits. Preview and screenshots are local artifacts, not release files.
