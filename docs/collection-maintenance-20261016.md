# Temporary user collection pause

Operator requested prioritizing staged historical recapture on 16/10/2026.

- An ignored local marker `.tmp-user-collection-maintenance/paused.json` gates new user collection only; no schema or database write is needed.
- A fresh quote with nonzero cost returns HTTP 503 with a maintenance message. Previously signed quotes are also checked before any Credit hold/job creation.
- Existing entitlements/read/history/settlement remain intact. No account permission changes, Credit changes, or cancellations.
- The shared source circuit stays closed and historical staging/system collection can continue. AI features are not paused through the broader wallet pause flag.
- Access policy dynamically reports the collection pause. The existing backend restart script validates this marker in addition to its unchanged registered arguments.
- 43 scoped tests PASS before enabling the marker, including stale quote blocking, no new Credit/job writes, and existing entitlement/history access.
- Initial activation requires restarting ONLY the public backend to load the new code. No worker restart or frontend deploy is required. Windows Task Scheduler is not accessible to the agent session, so activation must be confirmed from operator output plus a runtime policy check.
- Reopening requires the operator's decision and archiving/removing only this exact marker; never open the DVCQG safety circuit as a substitute.
