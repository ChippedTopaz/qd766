# Explicit TTHC collection flow — 2026-10-03

- Filters and existing-data reads remain GET-only. Only the explicit **Lấy dữ liệu** button sends a collection POST; all-procedure requests are not submitted by the UI.
- Public read-only access remains locked. This increment is for the office/admin workflow, not a release of paid access. Authentication/credits/payments remain unchanged.
- Single and filtered-batch submissions are guarded against double clicks. Active requests cannot be submitted again from the current selection; upstream job deduplication remains unchanged.
- Monitoring is independent of changing filters. Notices retain province, reporting period and TTHC code/name (or filtered count). Blocked jobs are still monitored; no circuit mutation is performed.
- Poll only local backend status, normally every 10 seconds, with retry backoff up to 60 seconds and 15-second read timeout. A failed status read is not a collection failure. Terminal success/failure/halt/cancellation ends polling. Success reloads saved data for the matching selection, bypassing the stale in-memory snapshot.
- Completion notices work in the open tab. OS notification is used only if permission was already granted. Tracking is currently in-memory: after reloading/closing the tab, check Vận hành; persistent per-account notifications belong to the later authenticated workflow.
- The legacy dashboard `period:formality` key may carry a different formalityId than the default selector. Normalization now keys snapshots by their actual formalityId rather than assigning the default TTHC's identity.

## Verification

87 Python tests, TypeScript build, tracker tests, actual renderer interaction tests, summary-only GET-only smoke test, Excel exporter tests passed. Renderer tests cover scope/TTHC/period changes without POST, wrong legacy ID rejection, explicit submission, double click, blocked-job monitoring and completion after period change.

`node tools/verify_formality_analysis.mjs` performed GET-only checks against saved office PostgreSQL data for Phú Thọ, TTHC 2.000815: May, June, August, September, Q3 and year 2026. Analysis, same-level peer calculation, score/component workbook generation and XLSX read-back passed for all six periods. These TTHC snapshots contain five supported groups; do not fabricate a sixth. This does not validate a new upstream collection or cross-province TTHC coverage.

Production deployment uses `tools/deploy_reviewed_frontend.ps1` with a backup. No production write or new real collection job was performed while implementing this change. End-to-end live collection and persistent notifications are not claimed as verified.
