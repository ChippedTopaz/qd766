import assert from 'node:assert/strict';
import {RecentDashboard} from '../dist/recent-dashboard.js';
let now=0;const cache=new RecentDashboard(30_000,2,()=>now);
const a={province:'a'};cache.set('a',a);cache.set('b',{});
assert.equal(cache.get('a'),a);cache.set('c',{});assert.equal(cache.get('b'),undefined);
now=30_000;assert.equal(cache.get('a'),undefined);
console.log('RECENT_DASHBOARD_OK: page-only, two-province bound, expiry and identity preserved');
