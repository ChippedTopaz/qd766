# Admin layout and load review — 2026-10-06

## Evidence

- Public GETs to production `admin.css` and `dist/admin.js` matched the pre-fix local files after normalizing line endings and removing the packaged source-map comment. Production admin HTML referenced `accounts-20261005`. This is not evidence of an incorrect admin deployment.
- Local mock names are shorter than real province/agency names. Automatic table widths and `display:flex` applied directly to the last table cell allowed production action buttons to wrap and inflate row height.
- Initial admin startup waited for directory, agency directory, accounts, invitations, audit, policy, another accounts request, Credit ledger, and shared registration lists. These hidden panels do not belong on the initial screen's critical path.
- The account API repeatedly read wallet enrollment, lots and cycles per account. Costs grew with the number of real users.

## Changes

- Fixed-width account columns; normal table-cell layout with a separate flex action wrapper. Long names wrap without dictating all column widths; narrow screens retain horizontal table scrolling and the existing mobile sidebar.
- Following authorization, directory, accounts and access policy load in parallel. Hidden invitation/audit/registration/Credit lists load when their menu opens. Concurrent identical GETs share only their in-flight promise; no completed wallet or authorization responses are cached.
- Agency choices load when needed for agency invitation/editing, not at initial account startup.
- Read-only batch projection uses at most four wallet/permission SELECTs, independent of account count, in addition to authentication, user and department queries. Legacy balances, subscription expiry, reserved Credit and default/explicit collection permissions retain their prior semantics. No schema migration, grants, admission or expiry mutations occur on GET.
- Admin stylesheet and entry-script versions changed to `admin-fast-20261006`.

## Validation and rollout

- Projection parity test covers 80 mixed source/legacy accounts, expired/live Credit lots, active/future/expired/no cycles, explicit and default collection permission. Four projection SELECTs; no writes.
- Credit shortcut regression includes deferred startup, no implicit grant, correct account/source and duplicate-submit protection.
- TypeScript compilation, all five admin frontend suites, bento/summary render regressions and all 268 Python tests passed. The mobile test now isolates the actual sidebar media block rather than inadvertently scanning unrelated desktop table rules.
- Static files can be synced to the local Google trial site; already-running Python processes still need a reviewed restart to use the new backend code. Production requires frontend deployment and public-backend restart. No production deployment or database alteration is performed by this change.
- These tests do not establish an authenticated production end-to-end latency. Measure with real account counts after restart/deployment; mock data alone is not a load benchmark.
