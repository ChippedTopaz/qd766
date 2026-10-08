import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../src/app.ts',import.meta.url),'utf8');
const section=source.slice(source.indexOf('function time(): string {'),source.indexOf('function peers(): string {'));
const expression=section.match(/\.sort\(\(a,b\)=>([^\n]+?)\)\.map/)?.[1];
assert.equal(expression,'periodOrder(b)-periodOrder(a)');
const orderExpression=source.match(/const periodOrder=.*?=>([^\n]+);/)?.[1];
assert.ok(orderExpression);
const periodOrder=new Function('item',`return ${orderExpression}`);
const comparator=new Function('a','b','periodOrder',`return ${expression}`);
for(const type of ['month','quarter','year']){
  const records=[{type,year:2025,value:12},{type,year:2026,value:1},{type,year:2026,value:2}];
  if(type==='quarter')records[0].value=4;
  if(type==='year'){records[0].value=null;records[1].value=null;records[2]={type,year:2027,value:null};}
  const original=JSON.stringify(records);
  const sorted=records.filter(()=>true).sort((a,b)=>comparator(a,b,periodOrder));
  assert.deepEqual(sorted,[records[2],records[1],records[0]],type+' newest first across years');
  assert.equal(JSON.stringify(records),original,'Source periods remain untouched');
}
assert.match(section,/previousAvailablePeriod\(data,p.id,state.scope\)/,'Previous-period calculation is unchanged');
assert.match(source,/\.sort\(\(a,b\)=>periodOrder\(a\)-periodOrder\(b\)\)\.slice\(-12\)/,'Trend chart remains chronological');
console.log('TIME_COMPARISON_ORDER_OK: newest first for month/quarter/year, prior-period and chart unchanged');
