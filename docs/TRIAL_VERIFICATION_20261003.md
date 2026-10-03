# Office trial verification — 2026-10-03

## Scope

Design branch only. Do not deploy to 8767 or push/merge until the user approves.
No new collection batch, schema migration, circuit change or account change in this verification.

## Preview boundary

The loopback preview at 8768 now forwards these four additional GET endpoints to the existing backend: system-status, collection-jobs, formality-batches, province-batches.
All four returned HTTP 200 and the operations screen rendered real PostgreSQL state.
POST remains blocked, including batch creation and circuit actions; non-allowlisted API GETs remain blocked. Tests verify blocked requests never reach the backend. Production/public access policy is unchanged.

## Data verification

- Existing annual refresh batch `8b023c82-022e-45f0-94aa-323e10cc3334` was running with 18/34 provinces completed, zero failed, at approximately 08:14 Vietnam time. This is progress, not final completion.
- Phú Thọ annual details were refreshed at 08:09. National province points were captured at 07:31. The UI and downloaded workbooks show both timestamps separately.
- The inventory still contains annual snapshots for all 34 provinces with all six root groups. Some snapshots have not yet been replaced by this batch.
- Annual inventory at this checkpoint showed missing transparency, digitization and satisfaction scores for the Quảng Ninh public administration center and the Đắk Lắk industrial parks board. Their cause is not established; do not fabricate values or classify them as transport failures.
- SELECT-only PostgreSQL HTTP-contract check passed all 15 Phú Thọ reporting periods: six datasets and 34 province ranking entries for every period.
- Real UI showed annual total 62.11, rank 17/34. Monthly comparison showed January–October in order with prior-month differences; missing prior-year comparison remained unavailable.

## Excel verification

The actual UI downloaded both the annual score workbook and component workbook for Phú Thọ. Read-back verified Vietnamese labels, reporting scope, both timestamps, six numeric group scores, and no scoreDelta/technical-key column. Existing layout remains unchanged.

Artifact Tool was used for read-only workbook inspection. Its importer displayed an empty shared-string cell as its string-table index; ExcelJS read-back confirmed the original component cell is empty. This is an inspection-tool discrepancy, not a confirmed exporter defect.

## Tests

- Python suite: 87 passed, including two new preview isolation tests.
- Excel export tests passed for Node and the self-hosted browser bundle.
- Leadership report tests passed: 34 provinces, department/commune scopes, six groups, tied ranks, null versus zero, XLSX read-back.
- No changes to frontend scoring formulas, data contracts or workbook design.

## Pending

Annual refresh completion and final completeness audit are still pending at this checkpoint. Production integration is explicitly waiting for approval; preserve `backup/pre-unified-style-20261003` and the existing pre-Bento baseline for rollback.
