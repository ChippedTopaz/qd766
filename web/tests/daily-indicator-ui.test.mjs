import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const provincial=process.argv.includes('--province');
const peerTitle=provincial?/So với tỉnh\/thành phố khác/:/So với đơn vị cùng cấp/;
const own=data.units.find(u=>u.departmentId===data.province.id&&provincial||!provincial&&u.departmentLevel==='COMMUNE');assert(own);
const template=structuredClone(Object.values(data.snapshots).find(s=>s.scope==='all'));
if(!provincial){const online=template.datasets.find(d=>d.group==='provide-online-tree').children.find(e=>e.departmentId===own.departmentId);online.parameters={};online.metrics=[];}
data.defaultUnitId=own.departmentId;data.periods=[{id:'month-2026-10',label:'Tháng 10/2026',type:'month',year:2026,value:10,provisional:true}];
data.snapshots={'month-2026-10:all':template};
const app={innerHTML:'',setAttribute(){},querySelectorAll(){return []}};
const control=dataset=>({dataset,handlers:{},addEventListener(k,fn){this.handlers[k]=fn},focus(){}});
let groups=[],modes=[],dates={},rows=[],ranges=[],scope=control({}),total=control({});
globalThis.document={title:'',querySelector(s){return s==='#app'?app:s==='#scope-select'?scope:s==='[data-score-total]'?total:null},querySelectorAll(s){
 if(s==='[data-group-detail]'){groups=[...new Set([...app.innerHTML.matchAll(/data-group-detail="([^"]+)"/g)].map(m=>m[1]))].map(groupDetail=>control({groupDetail}));return groups;}
 if(s==='[data-indicator-detail-tab]'){modes=[...app.innerHTML.matchAll(/data-indicator-detail-tab="([^"]+)"/g)].map(m=>control({indicatorDetailTab:m[1]}));return modes;}
 if(s==='[data-daily-indicator-date]'){dates={};return [...app.innerHTML.matchAll(/data-daily-indicator-date="([^"]+)"/g)].map(m=>{const c=control({dailyIndicatorDate:m[1]});dates[m[1]]=c;return c;});}
 if(s==='[data-daily-indicator-row]'){rows=[...app.innerHTML.matchAll(/data-daily-indicator-row="([^"]+)"/g)].map(m=>control({dailyIndicatorRow:m[1]}));return rows;}
 if(s==='[data-daily-indicator-range]'){ranges=[...app.innerHTML.matchAll(/data-daily-indicator-range="([^"]+)"/g)].map(m=>control({dailyIndicatorRange:m[1]}));return ranges;}
 return [];
}};
globalThis.window={setTimeout:(fn,ms)=>{const t=setTimeout(fn,ms);t.unref();return t;},clearTimeout};
globalThis.location={search:'?period=month-2026-10',hash:'',pathname:'/'};
let url='';globalThis.history={state:null,replaceState(_s,_t,u){url=u}};globalThis.scrollTo=()=>{};
const calls=[];let hold=null;
const source=(group,day)=>{
 const dataset=template.datasets.find(d=>d.group===group);const entity=structuredClone(provincial?dataset.root:dataset.children.find(e=>e.departmentId===own.departmentId));
 if(group==='formality-online-payment-tree')entity.parameters={totalDossierOnlinePaymentSuccess:1000+(Number(day.slice(-2))-11)*200,totalDossierFinancialObligation:1300+(Number(day.slice(-2))-11)*100,
  totalFeeDossierFormality:32,totalFeeFormality:40,totalDossierOnlineFormalityPaymentSuccess:32,totalFeeDossierFormalityDistinct:40};
 return entity;
};
globalThis.fetch=async(target,options)=>{
 calls.push({target,method:options?.method??'GET'});let body=[];
 if(target==='/api/v1/access-policy')body={publicReadOnly:true,loginRequired:true,googleLoginEnabled:true};
 else if(target==='/api/v1/auth/me')body={id:'own-account',name:'Viewer',provinceId:data.province.id,role:'user',accessTier:provincial?'province':'agency',unitId:own.departmentId,csrfToken:'test',credits:100};
 else if(target.startsWith('/api/v1/dashboard?'))body=data;
 else if(target.includes('/daily-indicator-comparison?')){
  const q=new URL(target,'https://example.test').searchParams,group=q.get('group'),current=q.get('current_date')??'2026-10-12',baseline=q.get('baseline_date')??'2026-10-11';
  if(hold)await hold.promise;
  const series=[];const cursor=new Date(baseline+'T00:00:00Z');
  while(cursor.toISOString().slice(0,10)<=current){const day=cursor.toISOString().slice(0,10);series.push({reportDate:day,capturedAt:null,entity:source(group,day),state:'available'});cursor.setUTCDate(cursor.getUTCDate()+1);}
  body={scope:'all',unitId:own.departmentId,unitName:own.departmentName,group,availableDates:Array.from({length:7},(_,i)=>`2026-10-${String(12-i).padStart(2,'0')}`),series,
   current:{reportDate:current,capturedAt:'2026-10-13T00:00:00Z',entity:source(group,current),state:'available'},
   baseline:{reportDate:baseline,capturedAt:'2026-10-12T00:00:00Z',entity:source(group,baseline),state:'available'}};
 }
 return {ok:true,status:200,json:async()=>structuredClone(body)};
};
const settle=async()=>{for(let i=0;i<10;i++)await new Promise(r=>setImmediate(r))};
await import('../dist/app.js?daily-indicator-test');await settle();
assert(!calls.some(c=>c.target.includes('daily-indicator-comparison')),'No daily-detail API at initial page load');
groups.find(g=>g.dataset.groupDetail==='formality-online-payment-tree').handlers.click();await settle();
assert.match(app.innerHTML,peerTitle);assert.equal(modes.length,2);
const selectionUrl=url;const latest=JSON.stringify(data.snapshots);
modes.find(m=>m.dataset.indicatorDetailTab==='daily').handlers.click();await settle();
assert.match(app.innerHTML,/daily-indicator-panel/);assert.doesNotMatch(app.innerHTML,/class="comparison-card/);
assert.match(app.innerHTML,/id="daily-indicator-detail"/);assert.doesNotMatch(app.innerHTML,/id="group-detail"/,'Daily cards must not inherit existing detail-table mobile grid rules');
assert.match(app.innerHTML,/\+200/);assert.match(app.innerHTML,/\+8,79 điểm %/);assert.match(app.innerHTML,/\+0,52 điểm/);
assert.equal(url,selectionUrl,'Comparison does not change the main selectors/URL');
assert.equal(JSON.stringify(data.snapshots),latest,'Comparison does not replace main snapshots');
let reads=calls.filter(c=>c.target.includes('daily-indicator-comparison'));assert.equal(reads.length,1);
rows.find(r=>r.dataset.dailyIndicatorRow==='3.6').handlers.click({target:{closest(){return null}}});await settle();
assert.match(app.innerHTML,/<tr class="daily-selectable-row daily-selected" data-daily-indicator-row="3\.6">/,'Clicking a numeric cell selects its whole indicator row');
assert.doesNotMatch(app.innerHTML,/daily-indicator-explanation|daily-explanation-row/);
const chart=app.innerHTML.split('<aside class="daily-indicator-chart"')[1];assert(chart);
assert.match(chart,/data-daily-combo-delta="200"/);assert.match(chart,/daily-combo-svg/);assert.match(chart,/\+200/);
assert.match(app.innerHTML,/data-calendar-open/);assert.match(app.innerHTML,/data-calendar-panel/);
assert.equal(calls.filter(c=>c.target.includes('daily-indicator-comparison')).length,1,'Changing chart indicator stays local');
rows.find(r=>r.dataset.dailyIndicatorRow==='3.5').handlers.click();await settle();
assert.match(app.innerHTML.split('<aside class="daily-indicator-chart"')[1],/data-daily-combo-delta="0"/);
assert.equal(calls.filter(c=>c.target.includes('daily-indicator-comparison')).length,1);
rows.find(r=>r.dataset.dailyIndicatorRow==='3.6').handlers.click();await settle();
dates.baseline.value='2026-10-09';dates.baseline.handlers.change();await settle();
assert(calls.some(c=>c.target.includes('baseline_date=2026-10-09')));assert.match(app.innerHTML,/09\/10\/2026/);
assert.match(app.innerHTML,/<tr class="daily-selectable-row daily-selected" data-daily-indicator-row="3\.6">/,'Selected chart indicator survives date change');
const readsBeforeRange=calls.filter(c=>c.target.includes('daily-indicator-comparison')).length;
assert.deepEqual(ranges.map(r=>r.dataset.dailyIndicatorRange),['7'],'Only complete available ranges are offered');
ranges[0].handlers.click();await settle();
assert.match(app.innerHTML,/data-daily-indicator-range="7" aria-pressed="true"/);
assert.match(app.innerHTML,/<tr class="daily-selectable-row daily-selected" data-daily-indicator-row="3\.6">/,'Quick range retains selected chart indicator');
const rangeChart=app.innerHTML.split('<aside class="daily-indicator-chart"')[1];
assert.deepEqual([...rangeChart.matchAll(/data-daily-combo-date="([^"]+)"/g)].map(m=>m[1]),Array.from({length:7},(_,i)=>`2026-10-${String(i+6).padStart(2,'0')}`));
assert.deepEqual([...rangeChart.matchAll(/data-daily-combo-delta="([^"]+)"/g)].map(m=>Number(m[1])),[200,200,200,200,200,200]);
assert.equal(calls.filter(c=>c.target.includes('daily-indicator-comparison')).length,readsBeforeRange+1,'One GET for full date range, not per day');
modes.find(m=>m.dataset.indicatorDetailTab==='current').handlers.click();await settle();
assert.match(app.innerHTML,peerTitle);assert.doesNotMatch(app.innerHTML,/daily-indicator-panel/);
groups.find(g=>g.dataset.groupDetail==='dossier-digitized').handlers.click();await settle();
assert.match(app.innerHTML,/data-indicator-detail-tab="current" aria-selected="true"/);
hold={};hold.promise=new Promise(resolve=>{hold.resolve=resolve});
modes.find(m=>m.dataset.indicatorDetailTab==='daily').handlers.click();await settle();
modes.find(m=>m.dataset.indicatorDetailTab==='current').handlers.click();hold.resolve();hold=null;await settle();
assert.doesNotMatch(app.innerHTML,/daily-indicator-panel/,'Late response does not switch away from current detail');
groups.find(g=>g.dataset.groupDetail==='provide-online-tree').handlers.click();await settle();
if(provincial){
 assert.match(app.innerHTML,/data-indicator-detail-tab="daily"/,'Provincial online detail has daily tab');
 modes.find(m=>m.dataset.indicatorDetailTab==='daily').handlers.click();await settle();
 assert.match(app.innerHTML,/daily-indicator-panel/);assert.match(app.innerHTML,/TTHC cung cấp DVCTT toàn trình/);
 assert(calls.some(c=>c.target.includes('daily-indicator-comparison')&&c.target.includes('unit_id='+own.departmentId)&&c.target.includes('group=provide-online-tree')));
}else{
 assert.doesNotMatch(app.innerHTML,/data-indicator-detail-tab="daily"/,'No online detail for agency: hide tab');
 assert(!calls.some(c=>c.target.includes('daily-indicator-comparison')&&c.target.includes('group=provide-online-tree')),'No empty online-detail GET');
}
scope.value='formality';scope.handlers.change({target:scope});await settle();
assert.doesNotMatch(app.innerHTML,/data-indicator-detail-tab="daily"/,'Formality scope never shows day detail');
assert(calls.every(c=>c.method==='GET'),'No collection/Credit mutation');
console.log(`DAILY_INDICATOR_UI_PASS ${provincial?'province':'agency'}: lazy, dates, snapshots unchanged, peer pane, stale response, online daily visibility, all-only, GET-only`);
