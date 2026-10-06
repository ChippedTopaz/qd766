# Release 2026-10-06 — performance and usability

Changes since 23bca6d:

- Compact initial dashboard: all historical scores/units retained; detailed
  metrics fetched only for the selected period through existing read-only API.
- Indexed per-group entity lookup; two recently opened provinces cached in page
  memory for 30 seconds, not persistent storage. Agency filtering is retained.
- Newest month/quarter/year selected independently of source array ordering.
  Newest options appear first. Explicit saved/user-selected periods are retained.
- Admin accounts show agency names, province/agency filters and a Credit shortcut.
  Sidebar placeholder is visible during initialization, including on mobile.
- Online indicators use supplied numerators/denominators for explanatory ratios;
  no unsupported allocation of component points, no provincial fallback for units.
- Formula maximums appear in each existing formula card, not a separate table.
  Six group selectors precede one collapsed guide; selecting a group scrolls to it.
- Collector/report boundary is 04:00 Vietnam; report date remains previous day.
  Dates before 2026-10-06 are excluded from daily comparison, not deleted.
  Annual overview uses a calendar with available-date bounds; period comparison
  menus retain their previous logic.

Validation: 267 backend tests, TypeScript build and 13 frontend test suites pass.
Fresh isolated Netlify packaging must exclude fixtures, secrets, maps and previews.
No migration is needed. No collection or Credit transactions are initiated by
release verification. Source dumps/checkpoints/backups are excluded from Git.

Production activation:

1. Push main to trigger the existing Netlify Git build; verify published index
   references dist/app.js?v=period-latest-20261006 and new modules are served.
2. Restart public backend with tools/restart_public_backend.ps1 so its process
   loads the latest modules; configuration checks must pass before stopping it.
3. Existing schedule has already been operator-verified for 07/10/2026 04:00.
   Do not run another collection or re-register other tasks during this release.
4. Authenticated acceptance: first load, uncached province switch, cached return,
   month/quarter changes, admin filters/Credit targeting and formula navigation.
   Backend microbenchmarks do not replace production end-to-end measurements.
