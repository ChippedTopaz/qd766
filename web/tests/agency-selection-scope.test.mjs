import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const snapshot=structuredClone(Object.values(data.snapshots).find(s=>s.scope==='all'));
const own=data.units.find(u=>u.departmentLevel==='COMMUNE');
const other=data.units.find(u=>u.departmentLevel==='COMMUNE'&&u.departmentId!==own?.departmentId);
assert(own&&other);
// Deliberately send extra units: the client must not treat comparison evidence as scope.
data.defaultUnitId=other.departmentId;
data.periods=[9,10].map(value=>({id:`month-2026-${value}`,label:`Tháng ${value}/2026`,type:'month',year:2026,value,provisional:false}));
data.snapshots={'month-2026-10:all':{...snapshot,detailsLoaded:false}};
const app={innerHTML:'',setAttribute(){}};
const controls=new Map();
function control(id){if(!controls.has(id))controls.set(id,{handlers:{},value:'',dataset:{},addEventListener(k,cb){this.handlers[k]=cb;}});return controls.get(id);}
const nav=control('peers');nav.dataset.nav='peers';
const forgedPeer=control('forged-peer');forgedPeer.dataset.peerUnit=other.departmentId;
globalThis.document={title:'',querySelector:s=>s==='#app'?app:['#unit-select','#period-value'].includes(s)?control(s):null,
  querySelectorAll:s=>s==='[data-nav]'?[nav]:s==='[data-peer-unit]'?[forgedPeer]:[]};
globalThis.TomSelect=class{constructor(){}on(){}destroy(){}};
globalThis.window={setTimeout:(fn,delay)=>{const timer=setTimeout(fn,delay);timer.unref();return timer},clearTimeout};
globalThis.location={search:`?unit=${other.departmentId}`,hash:'',pathname:'/'};
let savedUrl='';globalThis.history={state:null,replaceState(_s,_title,url){savedUrl=url;}};
globalThis.scrollTo=()=>{};
const calls=[];
globalThis.fetch=async url=>{
  calls.push(url);
  let body;
  if(url==='/api/v1/access-policy')body={publicReadOnly:true,loginRequired:true,googleLoginEnabled:true};
  else if(url==='/api/v1/auth/me')body={name:'Agency',role:'user',accessTier:'agency',provinceId:data.province.id,unitId:own.departmentId,csrfToken:'test',credits:100};
  else if(url.startsWith('/api/v1/dashboard?'))body=data;
  else if(url.includes('/selection?'))body={snapshot,metadata:{detailsAvailable:true}};
  else body=[];
  return {ok:true,status:200,json:async()=>structuredClone(body)};
};
async function settle(){for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r));}
function assertOwn(){
  assert.doesNotMatch(app.innerHTML,/Không thể tải dữ liệu/);
  const select=app.innerHTML.match(/<select id="unit-select">([\s\S]*?)<\/select>/)?.[1];
  assert(select,'agency selector exists');
  assert.equal([...select.matchAll(/<option value="([^"]+)"/g)].length,1);
  assert(select.includes(`value="${own.departmentId}" selected`));
  assert(!select.includes(`value="${other.departmentId}"`));
}
await import('../dist/app.js?agency-scope');await settle();
assertOwn(); // forged URL, compact hydration and initial selection
assert(calls.some(url=>url.includes('/selection?')));
control('#period-value').handlers.change({target:{value:'month-2026-9'}});await settle();
assertOwn(); // mergeUnits after a different month must keep one selectable unit
assert.equal(new URLSearchParams(savedUrl.split('?')[1]).get('unit'),own.departmentId);
control('#unit-select').handlers.change({target:{value:other.departmentId}});assertOwn();
forgedPeer.handlers.click();assertOwn();
nav.handlers.click();assertOwn();assert.match(app.innerHTML,/Bảng xếp hạng/);
assert(!app.innerHTML.includes(`data-peer-unit="${other.departmentId}"`));
console.log('AGENCY_SELECTION_SCOPE_OK: forged URL/change/peer rejected; compact hydration and period changes preserve assignment');
