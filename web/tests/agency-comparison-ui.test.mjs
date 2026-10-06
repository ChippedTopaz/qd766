// Actual app renderer, using fixture data and GET-only stubs. No source calls.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const original=Object.values(data.snapshots).find(s=>s.scope==='all');
const agency=data.units.find(u=>u.departmentLevel==='PROVINCE');
assert(agency);
data.defaultUnitId=agency.departmentId;
data.periods=[{id:'month-2026-09',label:'Tháng 9/2026',type:'month',year:2026,value:9,provisional:false}];
data.snapshots={'month-2026-09:all':original};
original.delivery={stale:true,message:'Dữ liệu cần cập nhật',detailsAvailable:true,result:'national-summary',capturedAt:'2026-10-05T00:00:00Z',detailsCapturedAt:'2026-10-04T00:00:00Z'};
const app={innerHTML:'',setAttribute(){}};
const control=dataset=>({dataset,handlers:{},addEventListener(kind,callback){this.handlers[kind]=callback}});
const nav=control({nav:'peers'});
let peerControls=[];
globalThis.document={title:'',querySelector:s=>s==='#app'?app:null,querySelectorAll(s){
  if(s==='[data-nav]')return [nav];
  if(s==='[data-peer-unit]'){
    peerControls=[...app.innerHTML.matchAll(/data-peer-unit="([^"]+)"(?: data-peer-group="([^"]+)")?/g)].map(m=>control({peerUnit:m[1],peerGroup:m[2]}));return peerControls;
  }
  return [];
}};
globalThis.window={setTimeout};globalThis.location={search:'?period=month-2026-09',hash:'',pathname:'/'};
let savedUrl='';globalThis.history={state:null,replaceState(_s,_title,url){savedUrl=url}};
globalThis.scrollTo=()=>{};
const calls=[];globalThis.fetch=async(url,options)=>{
  calls.push({url,method:options?.method??'GET'});
  const body=url==='/api/v1/access-policy'?{publicReadOnly:true}:url==='/api/v1/dashboard?fast=true&compact=true'?data:[];
  return {ok:true,status:200,json:async()=>structuredClone(body)};
};
await import('../dist/app.js');for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));
assert.doesNotMatch(app.innerHTML,/Không thể tải dữ liệu/);
nav.handlers.click();
assert.match(app.innerHTML,/<details class="comparison-notes"><summary>Lưu ý/);
assert.doesNotMatch(app.innerHTML,/<details class="comparison-notes" open/);
assert.match(app.innerHTML,/Bảng xếp hạng/);
assert.doesNotMatch(app.innerHTML,/data-agency-change|data-time-mode|Biến động ngày liền trước/);
assert.doesNotMatch(app.innerHTML,/Sở, ngành <span>|Xã, phường <span>/);
assert(!calls.some(c=>c.url.includes('daily-history')),'month/agency comparison must not load day observations');
assert.doesNotMatch(app.innerHTML,/Phân phối điểm|Quy mô hồ sơ tương đồng|Đơn vị liền kề/);
const group=peerControls.find(c=>c.dataset.peerGroup===data.groupOrder[1]&&c.dataset.peerUnit===agency.departmentId);
assert(group,'score cells link to the unit and group');group.handlers.click();
assert.match(app.innerHTML,/data-overview-tab="details" aria-selected="true"/);
assert.match(savedUrl,/period=month-2026-09/);assert.match(savedUrl,/scope=all/);
assert.equal(new URLSearchParams(savedUrl.split('?')[1]).get('unit'),agency.departmentId);
assert(calls.every(c=>c.method==='GET'));
console.log('AGENCY_COMPARISON_UI_OK: collapsed caveats, six-group table, period-preserving group navigation, GET-only');
