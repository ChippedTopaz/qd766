import assert from 'node:assert/strict';
import {latestPeriod} from '../dist/period-choice.js';
for(const [type,values] of [['month',[1,9,10]],['quarter',[1,2,4]],['year',[2024,2025,2026]]]){
 const items=values.map(v=>({id:String(v),type,year:type==='year'?v:2026,value:type==='year'?null:v}));
 for(const order of [items,[...items].reverse(),[items[1],items[2],items[0]]]){
  const before=JSON.stringify(order);
  assert.equal(latestPeriod(order).id,String(values.at(-1)));
  assert.equal(JSON.stringify(order),before);
 }
}
assert.equal(latestPeriod([]),undefined);
console.log('PERIOD_CHOICE_OK: latest month/quarter/year regardless of input ordering');
