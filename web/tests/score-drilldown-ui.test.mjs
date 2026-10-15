import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const template=structuredClone(Object.values(data.snapshots).find(s=>s.scope==='all'));
const national=process.argv.includes('--national');
const own=data.units.find(u=>u.departmentLevel===(national?'PROVINCE_TOTAL':'PROVINCE'));
const peer=national?{departmentId:'019d2be3-6a88-732b-8b17-b68020c8554a',departmentName:'Tỉnh xem thử khác',departmentLevel:'PROVINCE_TOTAL'}:data.units.find(u=>u.departmentLevel==='PROVINCE'&&u.departmentId!==own.departmentId);
assert(own&&peer);const restricted=process.argv.includes('--agency');
data.defaultUnitId=own.departmentId;
data.periods=[9,10].map(value=>({id:`month-2026-${value}`,label:`Tháng ${value}/2026`,type:'month',year:2026,value,provisional:value===10}));
data.periods.push(...[3,4].map(value=>({id:`quarter-2026-${value}`,label:`Quý ${value}/2026`,type:'quarter',year:2026,value,provisional:value===4})),
 ...[2025,2026].map(year=>({id:`year-${year}`,label:`Năm ${year}`,type:'year',year,value:null,provisional:year===2026})));
data.snapshots={};
function makeSnapshot(value){const s=structuredClone(template);s.delivery={detailsAvailable:true,result:'detail'};
 for(const d of s.datasets){for(const e of [d.root,...d.children]){e.apiScore=value;e.apiMaxScore=20;}}return s;}
data.snapshots['month-2026-9:all']=makeSnapshot(1);data.snapshots['month-2026-10:all']=makeSnapshot(2);
for(const p of data.periods.filter(p=>p.type!=='month'))data.snapshots[p.id+':all']=makeSnapshot(3);
const app={innerHTML:'',setAttribute(){},querySelectorAll(){return []}};
const control=dataset=>({dataset,handlers:{},addEventListener(k,cb){this.handlers[k]=cb},focus(){}});
const navTime=control({nav:'time'}),navOverview=control({nav:'overview'}),brief=control({});
const rankingPeriod=control({});
const rankingType=control({rankingPeriodField:'type'}),rankingYear=control({rankingPeriodField:'year'});
let scoreButtons=[],tabs=[],kind;
globalThis.document={title:'',querySelector(s){if(s==='#app')return app;if(s==='[data-action=brief]')return brief;if(s==='[data-ranking-period]')return rankingPeriod;return null;},querySelectorAll(s){
 if(s==='[data-nav]')return [navTime,navOverview];
 if(s==='[data-action=brief]')return [brief];
 if(s==='[data-ranking-period-field]')return [rankingType,rankingYear];
 if(s==='[data-score-detail]'){
  scoreButtons=[...app.innerHTML.matchAll(/data-score-detail="([^"]+)" title="([^"]*)" aria-label="[^"]*">([^<]*)/g)].map(m=>({...control({scoreDetail:m[1]}),title:m[2],text:m[3]}));return scoreButtons;
 }
 if(s==='[data-time-tab]'){tabs=['default','custom'].map(timeTab=>control({timeTab}));return tabs;}
 if(s==='[data-time-kind]'){kind=control({});return [kind];}
 return [];
}};
globalThis.window={setTimeout:(fn,delay)=>{const timer=setTimeout(fn,delay);timer.unref();return timer},clearTimeout};
globalThis.location={search:'?period=month-2026-10',hash:'',pathname:'/'};
let savedUrl='';globalThis.history={state:null,replaceState(_s,_t,url){savedUrl=url}};globalThis.scrollTo=()=>{};
const calls=[];
let failDaily=false,pendingDaily=null,failRanking=false,pendingRanking=null;
const benchmarkRows=()=>[own,peer].map((u,i)=>({rootDepartmentId:u.departmentId,provinceName:u.departmentName,totalScore:12+i,capturedAt:'2026-10-13T00:00:00Z',groups:Object.fromEntries(data.groupOrder.map(g=>[g,{score:2,maximum:20}]))}));
globalThis.fetch=async(url,options)=>{
 calls.push({url,method:options?.method??'GET'});let body=[];
 if(url==='/api/v1/access-policy')body={publicReadOnly:true,...(restricted||national?{loginRequired:true,googleLoginEnabled:true}:{})};
 else if(url==='/api/v1/auth/me')body={id:'reviewer',name:'Viewer',provinceId:data.province.id,role:national?'admin':'user',accessTier:national?'national':'agency',unitId:national?null:own.departmentId,credits:100,csrfToken:'test'};
 else if(url==='/api/v1/dashboard?fast=true&compact=true')body=data;
 else if(national&&url==='/api/v1/dashboard/provinces')body=[own,peer].map(u=>({id:u.departmentId,name:u.departmentName,available:true}));
 else if(national&&url.includes('/province-rankings?'))body=benchmarkRows();
 else if(national&&url.includes('/api/v1/dashboard?fast=true&compact=true&root_department_id=')){
  body=structuredClone(data);body.province={id:peer.departmentId,name:peer.departmentName};body.defaultUnitId=peer.departmentId;
  body.units=body.units.map(u=>u.departmentId===own.departmentId?{...u,departmentId:peer.departmentId,departmentName:peer.departmentName}:u);
  for(const s of Object.values(body.snapshots))for(const d of s.datasets){d.root.departmentId=peer.departmentId;d.root.departmentName=peer.departmentName;}
 }
 else if(url.includes('daily-history'))body={scope:'all',days:[7,8].map(day=>({reportDate:`2026-10-0${day}`,capturedAt:'2026-10-09T00:00:00Z',totalScore:(day-6)*6,rank:1,cohortSize:2,cohortKey:'review',groups:Object.fromEntries(data.groupOrder.map(g=>[g,{score:day-6,maximum:20}]))}))};
 else if(url.includes('/selection?')){
  const date=new URL(url,'https://test.local').searchParams.get('report_date');
  if(!date&&failRanking)return {ok:false,status:404,json:async()=>({detail:'Missing period'})};
  if(!date&&pendingRanking&&url.includes('year=2025'))await pendingRanking.promise;
  if(date&&failDaily)return {ok:false,status:404,json:async()=>({detail:'Missing saved day'})};
  if(date&&pendingDaily)await pendingDaily.promise;
  body={snapshot:makeSnapshot(date==='2026-10-07'?1:2),metadata:{reportDate:date,detailsAvailable:true,result:'detail'},benchmarks:national?benchmarkRows():[]};
  if(national){const root=new URL(url,'https://test.local').searchParams.get('root_department_id');for(const d of body.snapshot.datasets)d.root.departmentId=root;}
 }
 return {ok:true,status:200,json:async()=>structuredClone(body)};
};
const settle=async()=>{for(let i=0;i<10;i++)await new Promise(r=>setImmediate(r))};
await import('../dist/app.js?score-review');await settle();
assert.doesNotMatch(app.innerHTML,/Không thể tải dữ liệu/);
navTime.handlers.click();
let button=scoreButtons.find(b=>b.title.includes(data.groupLabels[data.groupOrder[0]])&&b.title.includes('Tháng 9/2026'));
assert(button);button.handlers.click();await settle();
assert.match(app.innerHTML,/data-overview-tab="details" aria-selected="true"/);
assert.equal(new URLSearchParams(savedUrl.split('?')[1]).get('period'),'month-2026-9');
assert.match(app.innerHTML,new RegExp(`data-group-detail="${data.groupOrder[0]}" aria-pressed="true"`));
navTime.handlers.click();
button=scoreButtons.find(b=>b.title.startsWith('Xem điểm tổng hợp')&&b.title.includes('Tháng 10/2026'));
assert(button);button.handlers.click();await settle();
assert.match(app.innerHTML,/data-score-total aria-pressed="true"/);
assert.match(app.innerHTML,/data-overview-tab="details" aria-selected="true"/);
navTime.handlers.click();tabs[1].handlers.click();kind.value='day';kind.handlers.change();await settle();
button=scoreButtons.find(b=>b.title.includes(data.groupLabels[data.groupOrder[0]])&&b.title.includes('07/10/2026'));
assert(button,'Saved-day score is clickable');button.handlers.click();await settle();
assert(calls.some(c=>c.url.includes('report_date=2026-10-07')));
assert.match(savedUrl,/report_date=2026-10-07/);assert.match(app.innerHTML,/Dữ liệu ngày 07\/10\/2026/);
assert.match(app.innerHTML,/data-overview-tab="details" aria-selected="true"/);
navTime.handlers.click();tabs[0].handlers.click();
assert(scoreButtons.some(b=>b.title.includes('Tháng 10/2026')&&b.text==='2,00'),'Original latest period restored after leaving day view');
assert(!savedUrl.includes('report_date'),'Leaving day view removes its URL selection');
for(const [type,label,period] of [['quarter','Quý 3/2026','quarter-2026-3'],['year','Năm 2025','year-2025']]){
 tabs[1].handlers.click();kind.value=type;kind.handlers.change();await settle();
 button=scoreButtons.find(b=>b.title.includes(data.groupLabels[data.groupOrder[0]])&&b.title.includes(label));
 assert(button,`${type} custom score is clickable`);button.handlers.click();await settle();
 assert.equal(new URLSearchParams(savedUrl.split('?')[1]).get('period'),period);
 navTime.handlers.click();
}
// Return to October so the leadership preview still verifies the original context.
tabs[1].handlers.click();kind.value='month';kind.handlers.change();await settle();button=scoreButtons.find(b=>b.title.startsWith('Xem điểm tổng hợp')&&b.title.includes('Tháng 10/2026'));
assert(button);button.handlers.click();await settle();
navOverview.handlers.click();assert(brief.handlers.click);brief.handlers.click();await settle();
assert.match(app.innerHTML,/ranking-report/);
const outsideUrl=savedUrl;
rankingType.value='quarter';rankingType.handlers.change();await settle();
assert.match(app.innerHTML.slice(app.innerHTML.indexOf('class="ranking-report"')),/Quý 4\/2026/);
rankingType.value='year';rankingType.handlers.change();await settle();
rankingYear.value='2025';rankingYear.handlers.change();await settle();
assert.match(app.innerHTML.slice(app.innerHTML.indexOf('class="ranking-report"')),/Năm 2025/);
assert.equal(savedUrl,outsideUrl,'Type and year controls leave main context unchanged');
for(const [id,label] of [['month-2026-9','Tháng 9/2026'],['quarter-2026-4','Quý 4/2026'],['year-2026','Năm 2026'],['month-2026-10','Tháng 10/2026']]){
 rankingPeriod.value=id;rankingPeriod.handlers.change({currentTarget:rankingPeriod});await settle();
 const ranking=app.innerHTML.slice(app.innerHTML.indexOf('class="ranking-report"'));
 assert(ranking.includes(label),`Ranking changes independently to ${id}`);
 assert(scoreButtons.some(b=>b.title.includes(label)),'Ranking detail links target the selected report period');
 assert.equal(savedUrl,outsideUrl,'Changing ranking period does not change main page URL');
 assert(calls.some(c=>c.url.includes('/selection?')&&c.url.includes('period_type='+id.split('-')[0])));
}
failRanking=true;rankingPeriod.value='quarter-2026-3';rankingPeriod.handlers.change({currentTarget:rankingPeriod});await settle();
assert.match(app.innerHTML,/Kỳ báo cáo được chọn chưa có dữ liệu xếp hạng/);assert.doesNotMatch(app.innerHTML,/<table class="leadership-table"/,'Missing period never falls back to latest');
failRanking=false;
pendingRanking={};pendingRanking.promise=new Promise(resolve=>{pendingRanking.resolve=resolve});
rankingPeriod.value='year-2025';rankingPeriod.handlers.change({currentTarget:rankingPeriod});await settle();
rankingPeriod.value='month-2026-9';rankingPeriod.handlers.change({currentTarget:rankingPeriod});await settle();
pendingRanking.resolve();await settle();pendingRanking=null;
assert.match(app.innerHTML.slice(app.innerHTML.indexOf('class="ranking-report"')),/Tháng 9\/2026/,'Late response cannot overwrite a newer period selection');
assert.equal(savedUrl,outsideUrl);
rankingPeriod.value='month-2026-10';rankingPeriod.handlers.change({currentTarget:rankingPeriod});await settle();
const modal=app.innerHTML.slice(app.innerHTML.indexOf('class="modal-backdrop"'));
if(restricted)assert(!scoreButtons.some(b=>b.title.includes(peer.departmentName)),'Peer business details never become clickable for agency account');
const row=restricted?own:peer;
if(process.argv.includes('--unit-name')){
 rankingPeriod.value='month-2026-9';rankingPeriod.handlers.change({currentTarget:rankingPeriod});await settle();
 button=scoreButtons.find(b=>b.title.startsWith('Mở Tổng quan')&&b.title.includes(row.departmentName));
 assert(button,'Unit name has an authorized overview link');button.handlers.click();await settle();
 assert.doesNotMatch(app.innerHTML,/ranking-report/);
 const query=new URLSearchParams(savedUrl.split('?')[1]);assert.equal(query.get('unit'),row.departmentId);assert.equal(query.get('period'),'month-2026-9');
 assert.match(app.innerHTML,/data-overview-tab="overview" aria-selected="true"/);
 if(national)assert.equal(query.get('province'),peer.departmentId);
 assert(calls.every(c=>c.method==='GET'));
 console.log('RANKING_UNIT_NAME_PASS: correct unit/province, independent report period, overview, permissions, GET-only');
 process.exit(0);
}
button=scoreButtons.find(b=>b.title.includes(row.departmentName)&&b.title.includes(data.groupLabels[data.groupOrder[1]]));
assert(button);button.handlers.click();await settle();
assert.doesNotMatch(app.innerHTML,/ranking-report/,'Preview dialog closes on navigation');
assert.equal(new URLSearchParams(savedUrl.split('?')[1]).get('unit'),row.departmentId);
if(national){assert.equal(new URLSearchParams(savedUrl.split('?')[1]).get('province'),peer.departmentId);assert(calls.some(c=>c.url.includes('/dashboard?fast=true&compact=true&root_department_id='+peer.departmentId)),'National report score switches to its own province');}
assert.match(app.innerHTML,new RegExp(`data-group-detail="${data.groupOrder[1]}" aria-pressed="true"`));
navTime.handlers.click();tabs[1].handlers.click();kind.value='day';kind.handlers.change();await settle();
button=scoreButtons.find(b=>b.title.includes(data.groupLabels[data.groupOrder[0]])&&b.title.includes('07/10/2026'));
assert(button);failDaily=true;button.handlers.click();await settle();
assert.match(app.innerHTML,/Chưa mở được chi tiết điểm/);assert.doesNotMatch(app.innerHTML,/class="panel group-detail/,'No latest detail fallback on 404');
failDaily=false;navTime.handlers.click();
// Navigating away while a day request is pending must not replace the latest snapshot.
tabs[1].handlers.click();kind.value='day';kind.handlers.change();await settle();
button=scoreButtons.find(b=>b.title.includes(data.groupLabels[data.groupOrder[0]])&&b.title.includes('07/10/2026'));
assert(button);pendingDaily={};pendingDaily.promise=new Promise(resolve=>{pendingDaily.resolve=resolve});
button.handlers.click();await settle();navTime.handlers.click();pendingDaily.resolve();await settle();pendingDaily=null;
tabs[0].handlers.click();assert(scoreButtons.some(b=>b.title.includes('Tháng 10/2026')&&b.text==='2,00'),'Abandoned day request cannot overwrite latest');
assert(calls.every(c=>c.method==='GET'),'No collection or Credit mutations');
console.log('SCORE_DRILLDOWN_UI_PASS '+(national?'national':restricted?'agency':'province')+': month/quarter/year, total, exact day, restore latest, report dialog/group/unit, missing-day and race guards, GET-only');
