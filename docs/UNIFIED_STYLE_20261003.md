# Unified frontend style — 2026-10-03

## Scope and recovery

- Work remains on `design/overview-bento-20261002`; production is unchanged.
- Baseline tag: `backup/pre-unified-style-20261003` at `926611a`.
- Preview: `http://127.0.0.1:8768/`, reading existing backend data without upstream refresh requests.
- To recover, create a separate checkout from the baseline tag; do not reset a dirty working tree or run the production updater from this design branch.

## Changes

- Shared `enterprise-mode` surfaces, typography, spacing, tables, buttons and notices across sidebar screens.
- Existing detail rows, columns, labels, formulas, comparisons and handlers are preserved.
- Responsive filters reserve readable space for period type/value/year; long selected agency names wrap rather than truncate.
- Gauge uses one three-stop gradient family according to the existing score classification: below 50 red; 50 to below 70 orange; 70 through 85 light blue; above 85 green. Both ends are round and colored. Missing values use a neutral track; zero has no filled value arc.
- Font stack reuses Inter when available, then Segoe UI/Arial; no external font dependency added. Numbers use tabular numerals.

## Verification

- TypeScript build and eight frontend test suites passed (analytics, Bento, CSV, Excel, formulas, leadership report, progress, summary-only UI).
- Python tests: 85 passed.
- Browser verification: real Cà Mau overview, group component table, time comparison, and 390px mobile filters with a long agency name. All seven component columns remain visible on the tested desktop width; mobile retains existing labeled row layout.
- No PostgreSQL schema, API contract, scheduler, circuit or credit changes.
