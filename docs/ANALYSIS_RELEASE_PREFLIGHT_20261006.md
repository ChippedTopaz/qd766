# Experimental analysis release preflight — 2026-10-06

## Result

Code and isolated frontend package pass automated checks. The additive analysis
migration has now been applied after the user supplied a fresh backup. Public
Gemini/wallet schema preflight passes. Operator activated/restarted the public
backend; direct loopback runtime policy confirms geminiAnalysisEnabled=true,
paidRequestsEnabled=true, sharedRegistrationEnabled=true, requests not paused.
Git push and Netlify deploy have NOT yet been performed. No real Credit
operation or real provider request was performed in this preflight. User reported
successful local analysis with Flash-Lite. Operator's task inventory confirms the
public backend and controlled worker both use the current repository checkout.
No D:\QD766 worker copy/update or worker restart is required for this release.

## UI

- Heading: Phân tích - đánh giá (Đang thử nghiệm).
- Removed the Gemini / 20 Credit-per-run subtitle from the page heading.
- Kept the explicit 20 Credit confirmation inside the existing styled dialog.
- Fixed uninitialized state access when binding analysis events on the login page.
- Updated compiled frontend and isolated local trial static assets.

## Verification

- Python unittest discovery: 289 tests passed (20.918 seconds).
- TypeScript build: passed.
- Frontend: 39 test files passed using required module arguments where applicable.
- Collection restore variant: passed; saved data reuse stays GET-only.
- Netlify fresh isolated package and allowlist test: passed; no fixtures, secrets
  or source maps. Existing netlify-public directory was not replaced.
- PowerShell scripts parsed successfully; git diff --check passed.
- Gemini tests mock HTTP only: explicit invocation, no auto-fetch, cancel before
  request, duplicate prevention, subscription-before-purchased allocation,
  one hold/charge or refund despite three provider attempts, account isolation,
  expiry/insufficient funds/CSRF, interrupted recovery, invalid AI output rejected.

## Read-only production preflight

- Gemini public settings construction: PASS.
- Initial public.alembic_version: 20261005_0017; analysis table absent.
- Backup supplied by operator: F:\QD766\backups\qd766-20261006-235136.dump,
  size 29608599; SHA256
  5BFF73313BF726275A4F8F6757309ACE18B9E66016014FC1C297DF59F76868A7.
- Hash matches supplied value and checksum sidecar; pg_restore --list and full
  decode to NUL passed. This is archive verification, NOT a restore rehearsal.
- Guarded migration applied 20261005_0017 -> 20261006_0018; adds analysis table,
  constraint and index only; no activation/backfill/financial operation.
- Public launcher with --real-wallet --shared-registration --gemini-analysis
  --check: PASS after migration, wallet/schema verified read-only.
- check_release_tasks.ps1: Task Scheduler access denied; no task changes made.

## Deployment gate / order

1. Fresh verified PostgreSQL backup; use existing restore-rehearsal procedure.
2. Review/apply 20261006_0018 using tools/migrate_gemini_analysis.py with a real
   backup dump and matching .sha256 sidecar. It does not activate the feature.
3. Re-run public launcher check with real-wallet/shared-registration/Gemini flags.
4. Explicitly register the public task with -RealWallet -SharedRegistration
   -GeminiAnalysis and restart using the reviewed script, retaining existing modes.
5. Publish the reviewed frontend through the existing Netlify workflow.
6. Smoke-test Google login, scope restrictions, absence of background analysis,
   one explicit successful analysis, saved-result read for free, and wallet ledger.
   Financial smoke tests require explicit authorization; use isolated trial first.

Keep .env.gemini server-side only. Provider quotas and billing are separate from
application Credit. No free-tier availability or production performance guarantee.
Disabling Gemini must not roll back/drop its table or erase financial records.
