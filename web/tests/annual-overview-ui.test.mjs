import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const original=Object.values(data.snapshots).find(s=>s.scope==='all');
data.periods=[{id:'year-2026',label:'Năm 2026',type:'year',year:2026,value:null,provisional:true}];
data.snapshots={'year-2026:all':original};
const app={innerHTML:'',setAttribute(){}};
const control=dataset=>({dataset,handlers:{},addEventListener(k,cb){this.handlers[k]=cb}});
const nav=[control({nav:'time'}),control({nav:'peers'})];
let dateControl;
globalThis.document={title:'',querySelector:s=>s==='#app'?app:null,querySelectorAll(s){
  if(s==='[data-nav]')return nav;
  if(s==='[data-annual-observation]'){dateControl=control({});dateControl.value='2026-10-04';return [dateControl];}
  return [];
}};
globalThis.window={setTimeout};globalThis.location={search:'?period=year-2026',hash:'',pathname:'/'};
globalThis.history={state:null,replaceState(){}};globalThis.scrollTo=()=>{};
const days=[['2026-10-05',72],['2026-10-04',70],['2026-10-03',71]].map(([reportDate,totalScore])=>({reportDate,totalScore,rank:null,cohortKey:'same',groups:{}}));
const calls=[];
globalThis.fetch=async url=>{calls.push(url);return {ok:true,json:async()=>structuredClone(url==='/api/v1/access-policy'?{publicReadOnly:true}:url.includes('daily-history')?{days}:url==='/api/v1/dashboard?fast=true'?data:[])}};
await import('../dist/app.js?annual-ui');for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r));
assert.match(app.innerHTML,/data-annual-observation/);assert.match(app.innerHTML,/\+2,00 điểm/);
dateControl.handlers.change();assert.match(app.innerHTML,/-1,00 điểm/);
assert.equal(calls.filter(url=>url.includes('daily-history')).length,1);
nav[0].handlers.click();assert.doesNotMatch(app.innerHTML,/data-annual-observation|data-time-mode/);
nav[1].handlers.click();assert.doesNotMatch(app.innerHTML,/data-annual-observation|data-agency-change/);
assert.equal(calls.filter(url=>url.includes('daily-history')).length,1);
console.log('ANNUAL_OVERVIEW_UI_OK: year-only hero, selected day, period-only comparison menus');
