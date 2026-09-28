# QĐ766 administrative-unit analytics frontend

This frontend is a TypeScript analytical workspace for province-wide results,
provincial departments, communes, and wards. It uses normalized M0 snapshots
and treats scores published by the source system as authoritative.

```text
npm install
npm run build
npm run serve
```

Open `http://127.0.0.1:8766`. The build regenerates `web/data/snapshots.json`
from the raw fixtures and type-checks the UI. `npm run serve` starts the website
and the on-demand data API together. Install `tools/requirements-server.txt`
on the application server. Set `QD766_DATABASE_URL` to enable PostgreSQL; when
it is absent, the development server uses the versioned file cache.

The period selector reads available months, quarters and years from the API.
Selecting a missing period starts one cache-aside collection; subsequent users
reuse the complete version. The application does not infer unverified scoring
formulas and does not combine unlike period types into a false time series.
