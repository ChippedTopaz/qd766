import assert from 'node:assert/strict';
import {onlineIndicators} from '../dist/online-indicators.js';
const p={authorityCount:49,partialCount:0,fullCount:49,onlineDossierCount:370,onlineServiceTotal:1881,
channelOnlineSum:197476,channelDirectSum:141,channelPostalSum:0,channelTotalSum:197617,onlineOnTimeSum:179061,onlineOverdueSum:18415};
const rows=onlineIndicators(p);
assert.deepEqual(rows.map(r=>r.ratio===null?null:Number(r.ratio.toFixed(2))),[0,100,0,99.93,0.07,90.67,9.33,19.67]);
assert.equal(rows[5].denominator,197476);
assert.deepEqual(onlineIndicators({}),[]);
assert.equal(onlineIndicators({authorityCount:0,fullCount:0}).find(r=>r.name.includes('toàn trình')).ratio,null);
assert.equal(onlineIndicators({authorityCount:49}).find(r=>r.name.includes('toàn trình')).numerator,null);
assert.equal(onlineIndicators({...p,partialCount:50})[2].ratio,null);
assert(rows.every(r=>!('score' in r)),'Never infer component points from ratios');
console.log('ONLINE_INDICATORS_OK: Lang Son ratios match screenshots; missing/zero/inconsistent denominators never fabricate points');
