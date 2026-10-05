# Dashboard performance update — 2026-10-05

The overview and province switch retain all period histories, groups, metrics,
parameters, exports and existing access boundaries. No database migration or
collection change is required.

Changes:

- Select the newest complete immutable snapshot ID for each logical period/scope
  in SQL before hydrating datasets, entities and metrics. Older versions remain
  stored for daily history, but are not loaded and then discarded by the dashboard.
- Browser requests opt into `fast=true`: serialize the already JSON-native,
  agency-filtered payload directly, avoiding a second recursive conversion.
  The default API contract and direct Python callers remain compatible.
- Compress only dashboard GET responses with gzip level 1, negotiated using
  Accept-Encoding. Authentication/invitation endpoints are excluded. Preserve
  private cache headers and Vary: Accept-Encoding.
- Bust the frontend script version for this update.

Read-only measurement on the same Phu Tho database (15 output periods):

| Measurement | Before | After |
| --- | --- | --- |
| Cold dashboard construction | 4.002 s, without JSON encoding | 2.199 s, including JSON encoding |
| Transfer size | 14.246 MiB, JSON with whitespace | 1.090 MiB, gzip level 1 |
| Compression time | — | 0.015 s |
| Cache-hit JSON response construction | — | 0.166 s |

These are local diagnostic measurements, not end-to-end production latency
guarantees. Internet, Netlify/Cloudflare proxy behavior and browser rendering must
be measured again after rollout. Server restart activates SQL/compression; the
frontend deployment activates the serialization fast path. Apply backend first.
No task restart, production push, or paid data request is performed by this patch.
