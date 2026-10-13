import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const app=readFileSync(new URL('../src/app.ts',import.meta.url),'utf8');
assert.match(app,/let maximumPendingRequests=3;/);
assert.match(app,/maximumPendingRequests=body.maximumPendingRequests!/);
assert.match(app,/pendingRequestCount>=maximumPendingRequests/);
assert.match(app,/\$\{int\(pendingRequestCount\)\}\/\$\{maximumPendingRequests\}/);
assert.doesNotMatch(app,/Tối đa 2 yêu cầu|\$\{int\(pendingRequestCount\)\}\/2/);
console.log('PENDING_LIMIT_UI_PASS: fallback 3, backend authoritative limit, dynamic count and warning');
