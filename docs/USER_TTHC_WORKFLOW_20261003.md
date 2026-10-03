# Account-owned TTHC workflow — 2026-10-03

## Shipped implementation

- Overview separates scope from a searchable **Thủ tục đã khai thác** selector and always provides an acquisition entry point. Previously purchased datasets are GET-only on re-open. URL remembers province, period, unit and TTHC; startup rechecks the account's library before restoring the selection.
- Acquisition is a dedicated sidebar workspace with **Tạo yêu cầu** and **Yêu cầu của tôi**. Domain/Lĩnh vực is searchable with TomSelect. Filters and procedure selection create no collection job or credit mutation.
- Explicit quote and confirmation are separate. The backend computes cost from account ownership only, not shared data availability. Signed quotes bind account, province, period, selected IDs, price and expiry; POST requires session CSRF. Batch confirmation covers up to 50 procedures; narrow filters beyond this safety limit.
- Existing paid request/ledger/notification tables are reused; no schema migration was added. Each account gets its own persistent entitlement and transaction history. Requests by separate accounts share a collection job or saved snapshot but each pays. Reopening an already acquired dataset is free. Financial writes are atomic and serialized per account.
- Worker releases pending credit holds if the circuit is open, without altering the circuit or jobs. Existing success/failure settlement remains authoritative. Persisted notifications produce a compact unread badge, with account-scoped read acknowledgement. Completion toast is temporary and does not push dashboard content down.
- API checks ready entitlement BEFORE serving selection/cache data. Public raw jobs/snapshots, global office library, cross-province catalog and TTHC rankings remain denied. Account catalog availability contains only its own acquired procedures, never another account's cache availability.
- Office operator mode still works without enabling login/credit: it has a clearly labeled administrative library/history and no pretend credit charge. This is not a simulation of separate account authorization.

## Verification

- 96 Python tests passed, including nine new account/API tests. Separate users pay for a shared cached dataset/shared queued job; same-account duplicate/replay does not pay again; CSRF, tampered/cross-account quotes, wrong period and unauthorized cached reads are blocked; multi-item insufficient-credit writes roll back; circuit holds are refunded. Notification acknowledgement is account-scoped and locked account balances refresh stale identity-map values.
- Real renderer tests passed: scoped library, explicit quote/confirmation, double-click protection, history, no admin request endpoints in paid mode, URL restoration without POST and no duplicate full-width notices. Existing analytics, Bento, formulas, Excel and leadership report tests passed.
- READ ONLY PostgreSQL checks verified the new office library and correct snapshot identity for Phú Thọ: year 2026 has four stored TTHCs, September one, October zero at this audit. No new crawl, test account, production credit adjustment or production login setting was created.
- Paid-account tests use isolated SQLite and simulated sessions. Live Google OAuth, PostgreSQL multi-worker credit contention, authenticated HTTPS browser tests and live upstream collection remain rollout checks, not claimed as passed.

## Rollout

Production 8767 is unchanged until backend+frontend deployment and restart. Do NOT deploy only frontend: its library/history rely on new APIs. Existing `update_qd766.ps1` performs the full update, database backup and restart. Before copying it also saves the deployed web/source/tools/configuration into an ignored local `.tmp-application-backups` folder and prints its location; configuration backups must never be published. Source rollback tag: `backup/pre-user-tthc-workflow-20261003`. `.tmp-*` QA/backup folders and Netlify output are excluded from deployment copy.

Do not enable paid requests on the current office operator instance automatically. The authenticated instance requires reviewed HTTPS Google OAuth configuration, account province assignments and an agreed price:

```text
QD766_PUBLIC_READ_ONLY=true
QD766_REQUIRE_LOGIN=true
QD766_PAID_REQUESTS_ENABLED=true
QD766_FORMALITY_CREDIT_COST=<approved positive integer>
QD766_TRIAL_CREDITS_ENABLED=true
```

All defaults remain disabled/unset; secrets belong only in the local configuration. Trial users may stay on the free plan with administrator-supplied credits. Payment/SePay is not implemented in this increment.
