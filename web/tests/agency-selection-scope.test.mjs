import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const snapshot=structuredClone(Object.values(data.snapshots).find(s=>s.scope==='all'));
const own=data.units.find(u=>u.departmentLevel==='COMMUNE');
const other=data.units.find(u=>u.departmentLevel==='COMMUNE'&&u.departmentId!==own?.departmentId);
assert(own&&other);
const digitized=snapshot.datasets.find(d=>d.group==='dossier-digitized');
const ownEntity=digitized.children.find(e=>e.departmentId===own.departmentId);
const otherEntity=digitized.children.find(e=>e.departmentId===other.departmentId);
assert(ownEntity&&otherEntity);
ownEntity.metrics.push({code:'comparison-test',name:'Chỉ tiêu đối chiếu thử',apiScore:1,apiMaxScore:4,numerator:10,denominator:40,ratio:25,extras:{}});
for(const dataset of snapshot.datasets)for(const entity of dataset.children){
  if(entity.departmentId!==own.departmentId){entity.metrics=[];entity.parameters={};}
}
otherEntity.comparisonPoints={'raw:comparison-test':{score:2,maximum:4}};
// Deliberately send extra units: the client must not treat comparison evidence as scope.
data.defaultUnitId=other.departmentId;
data.periods=[9,10].map(value=>({id:`month-2026-${value}`,label:`Tháng ${value}/2026`,type:'month',year:2026,value,provisional:false}));
data.snapshots={'month-2026-10:all':{...snapshot,detailsLoaded:false}};
const app={innerHTML:'',setAttribute(){}};
const controls=new Map();
function control(id){if(!controls.has(id))controls.set(id,{handlers:{},value:'',dataset:{},addEventListener(k,cb){this.handlers[k]=cb;}});return controls.get(id);}
const nav=control('peers');nav.dataset.nav='peers';
const forgedPeer=control('forged-peer');forgedPeer.dataset.peerUnit=other.departmentId;
const group=control('group');group.dataset.groupDetail='dossier-digitized';
const metric=control('metric');metric.dataset.metricDetail='raw:comparison-test';
globalThis.document={title:'',querySelector:s=>s==='#app'?app:['#unit-select','#period-value'].includes(s)?control(s):null,
  querySelectorAll:s=>s==='[data-agency-level]'?['PROVINCE','COMMUNE'].map(level=>{const item=control('level-'+level);item.dataset.agencyLevel=level;return item}):s==='[data-nav]'?[nav]:s==='[data-peer-unit]'?[forgedPeer]:s==='[data-group-detail]'?[group]:s==='[data-metric-detail]'?[metric]:[]};
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
function assertMetricComparison(){
  group.handlers.click();metric.handlers.click();assertOwn();
  const comparison=app.innerHTML.match(/<aside class="comparison-card metric-comparison">([\s\S]*?)<\/aside>/)?.[1];
  assert(comparison,'detail score comparison must exist for agency scope');
  assert(comparison.includes(other.departmentName),'peer is available for score comparison');
  assert(comparison.includes('2,00'),'peer component score is displayed');
  assert(!app.innerHTML.includes(`data-peer-unit="${other.departmentId}"`));
}
assertMetricComparison();
control('#period-value').handlers.change({target:{value:'month-2026-9'}});await settle();
assertOwn(); // mergeUnits after a different month must keep one selectable unit
assertMetricComparison();
assert.equal(new URLSearchParams(savedUrl.split('?')[1]).get('unit'),own.departmentId);
control('#unit-select').handlers.change({target:{value:other.departmentId}});assertOwn();
forgedPeer.handlers.click();assertOwn();
nav.handlers.click();assertOwn();assert.match(app.innerHTML,/Bảng xếp hạng/);
assert(!app.innerHTML.includes(`data-peer-unit="${other.departmentId}"`));
const escape=value=>value.replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
for(const level of ['PROVINCE','COMMUNE']){
  assert(app.innerHTML.includes(`data-agency-level="${level}"`),'Both aggregate comparison levels available');
  control('level-'+level).handlers.click();assertOwn();
  const units=new Map(snapshot.datasets.flatMap(dataset=>dataset.children).filter(entity=>entity.departmentLevel===level).map(entity=>[entity.departmentId,entity]));
  for(const entity of units.values())assert(app.innerHTML.includes(escape(entity.departmentName)),'Every province peer is listed: '+entity.departmentName);
  assert(!app.innerHTML.includes(`data-peer-unit="${other.departmentId}"`),'Other agency scores are not links to private details');
}
forgedPeer.handlers.click();assertOwn();
console.log('AGENCY_SELECTION_SCOPE_OK: all province aggregate peers in both levels; own-only detail selector; forged URL/change/peer rejected; component comparison preserved');
