# On-demand analysis — implementation and activation gate

Status: implemented behind configuration, NOT deployed/activated on office DB.
No real provider call or real Credit operation performed during development.

## Approved rules

- User explicitly opens Analysis/Evaluation and confirms 20 Credit per run.
- No Gemini call, paid analysis request, or automatic analysis fetch on page/tab load,
  province/period changes, login, scheduled collection, or background polling.
- Active subscription required, including admin/national accounts; no fee bypass.
- Source-wallet subscription Credit first, purchased Credit second; reserve 20,
  charge atomically with valid persisted result, refund on provider/schema failure.
- Existing saved results are free; reanalysis requires new explicit confirmation.
- Same account/token/context replays do not call provider or charge again.
- One running analysis per account, two simultaneous calls per backend process.
- Data is selected/authorized by backend, never supplied as browser-made statistics.
- First release supports all-TTHC scope only. Private TTHC scope remains disabled.
- totalReceived = totalOnTime + totalOverdue. On-time/overdue include BOTH completed
  and pending cases. Explicit contradictory counts block before reserving Credit.
- Overdue affects satisfaction; on-time cases with dissatisfaction also affect it.
  Never invent exact satisfaction point loss or double count unsupported cohorts.
- In-period missing output/payment may be explained by cases not yet at that stage;
  aggregated data cannot prove that explanation or identify individual cases.
- Daily decline: three consecutive real dates, equal maxima, each decline >=0.05.
  These are configurable-in-code initial heuristic thresholds, NOT official policy.
  Changed source formulas cannot be reliably detected from scores alone; daily
  findings explicitly require source-formula review and remain advisory.
- All source facts, titles, evidence, classification remain deterministic. Gemini
  recommends actions only; output validated for exact finding IDs, count, lengths,
  no invented numeric facts/HTML/URLs. Semantic recommendations remain advisory.
- Null/zero preserved; component score thresholds require positive known maximum.

## Activation prerequisites (do not paste secrets into chat or Git)

1. Back up office PostgreSQL and verify restore using existing reviewed procedure.
2. Review additive migration `20261006_0018`; migrate only after approval, preferably
   rehearse on restored isolated database first. No account backfill/financial changes.
   Guarded helper: `python tools/migrate_gemini_analysis.py --backup VERIFIED.dump
   --confirm`; requires fresh checksum sidecar. Without --confirm no DB connection.
3. Configure backend secrets privately. Public/local reviewed launchers read ONLY
   `.env.gemini` (copy `.env.gemini.example`; Git ignores the real file), with exactly
   `QD766_GEMINI_API_KEY` and `QD766_GEMINI_MODEL`. Public registration requires
   `-RealWallet -GeminiAnalysis` explicitly, restart preserves this flag and checks
   runtime policy. Local launcher requires `--source-wallet --gemini-analysis`:
   real provider, simulated Credit, isolated schema. Neither launcher inherits AI
   enablement from ordinary office settings. Generic app configuration supports:
   `QD766_GEMINI_API_KEY`, `QD766_GEMINI_MODEL` (reviewed generateContent-compatible
   model with structured output), `QD766_GEMINI_ANALYSIS_ENABLED=true`.
   Missing configuration returns 503 before hold, never consumes Credit.
4. Enable only on isolated local trial first; API billing/privacy approval required.
   Send only public aggregated indicators and findings, never emails, names of
   account owners, identity documents, case identifiers, or raw response paths.
5. Exercise real provider success, invalid/blocked response, timeout, repeated POST,
   expired subscription, insufficient Credit, refunds, and ownership restrictions.
6. Deploy code/frontend and restart reviewed public backend only after acceptance.

## Interruptions / operations

Provider timeout is 75 seconds per HTTP operation. On an explicit HTTP 503 only,
the same user-confirmed analysis retries at most twice, waiting 2 then 4 seconds
(at most three provider calls). No automatic retry for timeouts/network errors,
auth/quota errors, invalid output or other status codes; no model fallback.
All attempts share one reservation and one saved analysis. Charge 20 Credit once
only on valid persisted success, otherwise refund once. Provider quota/billing
may count retries independently of application Credit; no free-API guarantee.
DB transaction is committed/closed before outbound HTTP; no locks held while waiting.
Backend/network interruption may leave a reserved hold, never an unrecorded charge.
Same-account running jobs older than five minutes are refunded idempotently on
explicit analysis POST. Read latest to restore request token after browser reload,
then Continue to reconcile; GETs remain read-only. Operation script below can refund
stale holds for all accounts after inspecting records; no collection jobs affected.
Recovery: `python tools/recover_gemini_analyses.py --env-file PATH` is read-only;
add `--confirm-refunds` only after reviewing stale counts and DB target.
Provider exception messages/bodies/keys/prompts are never returned to user or logged.
Safe logs include retry attempt/delay/status and terminal exception type/status/job ID.

This release does not run a dedicated distributed job worker: process-local capacity
limit assumes the current single backend process. Multi-process deployment needs a
global admission mechanism. UI uses saved results, no automatic polling.

## API

POST `/api/v1/me/analysis`: selection rootDepartmentId/unitId/periodType/year/
periodValue, UUID token, expectedCredits=20, authenticated cookie and CSRF header.
GET `/api/v1/me/analysis/latest`: same context in snake_case query parameters.
GET is account-owned, free and does not grant cycles/expire Credit/mutate data.
