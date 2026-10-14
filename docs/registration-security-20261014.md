# Registration input hardening — 14/10/2026

## Finding and scope

A pending public-registration name contained a SQL-shaped string (`'and 1=1`). Registration persistence, lookup and review use SQLAlchemy bound expressions; the name was persisted as text. This is a suspicious input, not proof of successful SQL injection. No string-built SQL using profile input was found in the reviewed registration/auth/admin flow; admin registration rendering already HTML-escapes fields. This is a scoped code review and regression test, not a full penetration test or a guarantee against unrelated vulnerabilities.

The reported account was separately inspected and contained in production under explicit user authorization: pending registration rejected, account disabled, sessions revoked, original submission preserved, AdminAudit recorded. It had no admitted access, subscription cycles or wallet events. Exact identity, local incident script and database dump remain outside Git/public packaging.

## Changes

- Full-name validation on backend and frontend allows Unicode letters/combining marks, spaces, initials, hyphens and apostrophes, preserving Vietnamese and names such as O'Connor. Names start with a letter; numbers, markup, operators and control/zero-width characters are rejected. NFC normalization applies only to newly submitted valid names.
- Admin approval validates existing public-profile full names before granting admission or Credit. Invalid pending names can still be rejected without rewriting historical evidence. Existing legacy shared-invite registrations without profile names keep their flow.
- Prepared/bound SQL remains the actual injection boundary. Name allowlisting is profile validation, not a generic SQL-keyword blacklist. Legitimate apostrophes are not banned. SQL-shaped workplace text remains bound data and HTML-escaped, as demonstrated by tests.
- Includes the separately requested removal of the daily-comparison cumulative-change footnote; calculation, date/chart logic and data remain unchanged.
- No new dependency, schema migration, query, polling or background task. Validation is bounded by the existing 160-character name limit; no Credit/plan, collection/worker/schedule/formula changes.

## Verification

- 59 backend tests PASS across public/shared registration, trial administration, security boundaries, Google login and local Google guard.
- TypeScript build PASS. Seven frontend test files plus province daily-indicator UI profile PASS.
- Tests cover direct API malformed-name submissions returning 422 without persisting a profile or Credit, Unicode/NFD/legitimate apostrophes, malicious old-name approval blocked before any grants, explicit rejection, disabled-account session/OAuth denial, and SQL capture proving profile values travel as parameters rather than executable SQL. Admin HTML escaping regression PASS.
- Public launcher configuration/schema check PASS; no provider crawl or real Google login executed.
- PostgreSQL backup before containment: 75,656,490 bytes, SHA256 `26A2A6436ADF67A801E34C9A2856835F5A7830149E073840134A19CB7F9CD1E6`. Location is local `.tmp-security-registration-20261014/database/qd766-20261014-075225.dump`.

Reference: [OWASP SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html): parameterized queries are the primary boundary; field validation is supplementary.

## Deployment gate

Account containment is already committed to the production database. Code hardening is not active until the existing public backend is restarted. Agent restart attempt was denied by CIM/Task Scheduler before service changes. User must run the reviewed restart script and send PUBLIC_BACKEND_READY/PUBLIC_RUNTIME_POLICY; frontend push remains gated on readiness. No worker restart needed. Roll back code only if necessary; do not restore the full live database or automatically reactivate the contained account.
