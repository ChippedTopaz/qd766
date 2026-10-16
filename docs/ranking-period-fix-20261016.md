# Ranking movement between periods

- Month and quarter rankings compare the immediately preceding same-type period, including year boundaries. Missing adjacent periods are not replaced with older available periods.
- Read the existing saved dashboard selection for the preceding period, same root, scope, formality and unit level. National comparison uses saved province benchmarks; no collection or Credit writes.
- Populate total score change, group score colors and total rank movement. Rank movement is prior rank minus current rank; require identical complete-score unit cohorts. Ties retain existing competition ranks. Missing data stays unavailable, never zero.
- No dependency on archived daily observations; year/all-scope daily comparison remains unchanged.
- On opening a month/quarter ranking, refresh its saved current selection and baseline. Period changes load the same pair. At most eight baseline contexts retained; no polling, stale async completions only update their own cache and cannot redraw a different selection.
- Existing sorting, group ordering, score/name drilldown and Excel rendering retained.
- TypeScript and five test files PASS: ranking-period, ranking-daily, leadership-report, group-display-order, score-drilldown.
- Local implementation only at this checkpoint; no production restart, push, database migration or data replacement performed for this fix.
