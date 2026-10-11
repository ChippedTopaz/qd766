import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const source=Object.values(data.snapshots).find(s=>s.scope==='all');
const communes=data.units.filter(u=>u.departmentLevel==='COMMUNE').slice(0,8),own=communes[0];
data.units=[data.units[0],...communes,...data.units.filter(u=>u.departmentLevel==='PROVINCE').slice(0,1)];
data.periods=[{id:'month-2026-10',label:'Tháng 10/2026',type:'month',year:2026,value:10,provisional:true}];
for(const g of source.datasets)for(const [i,u] of communes.entries()){
 const e=g.children.find(e=>e.departmentId===u.departmentId);e.apiScore=10+i;e.apiMaxScore=20;
 if(g.group==='dvc-progress-tree')e.parameters.totalReceived=[1000,800,1200,799,1201,900,1100,1000][i];
}
data.snapshots={'month-2026-10:all':source};
for(const g of source.datasets)g.children=g.children.filter(e=>data.units.some(u=>u.departmentId===e.departmentId));
const app={innerHTML:'',setAttribute(){}};
const control=dataset=>({dataset,handlers:{},addEventListener(k,cb){this.handlers[k]=cb}});
const nav=control({nav:'peers'});let tabs=[],levels=[],filter,choices=[],save,search,sorts=[];
globalThis.document={title:'',querySelector(s){if(s==='#app')return app;if(s==='[data-watch-search]'){search={...control({}),focus(){},setSelectionRange(){}};return search}if(s==='[data-watch-similar]'){filter=control({});return filter}if(s==='[data-watch-save]'){save=control({});return save}return null},querySelectorAll(s){
 if(s==='[data-nav]')return [nav];if(s==='[data-agency-tab]'){tabs=['watch'].map(agencyTab=>control({agencyTab}));return tabs}
 if(s==='[data-agency-level]'){levels=['PROVINCE','COMMUNE'].map(agencyLevel=>control({agencyLevel}));return levels}
 if(s==='[data-watch-sort]'){sorts=['total',...data.groupOrder].map(watchSort=>control({watchSort}));return sorts}
 if(s==='[data-watch-unit]'){choices=[...app.innerHTML.matchAll(/data-watch-unit="([^"]+)"[^>]*>/g)].map(m=>({...control({watchUnit:m[1]}),checked:m[0].includes('checked'),disabled:m[0].includes('disabled')}));return choices}return [];
}};
const store=new Map();globalThis.localStorage={getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v)};
globalThis.window={setTimeout:(fn,delay)=>{const t=setTimeout(fn,delay);t.unref();return t},clearTimeout};globalThis.location={search:'?period=month-2026-10&unit='+own.departmentId,hash:'',pathname:'/'};globalThis.history={state:null,replaceState(){}};globalThis.scrollTo=()=>{};
let serverIds=[];const watchCalls=[];
globalThis.fetch=async(url,options={})=>{
 let body=[];
 if(url==='/api/v1/access-policy')body={publicReadOnly:true,googleLoginEnabled:true};
 else if(url==='/api/v1/auth/me')body={id:'account-A',name:'Agency',role:'user',accessTier:'agency',provinceId:data.province.id,unitId:own.departmentId,csrfToken:'test',credits:100};
 else if(url==='/api/v1/dashboard?fast=true&compact=true')body=data;
 else if(url.startsWith('/api/v1/me/agency-watch')){
  watchCalls.push({url,options});if(options.method==='POST')serverIds=JSON.parse(options.body).unitIds;
  body={unitIds:serverIds};
 }
 return {ok:true,json:async()=>structuredClone(body)};
};
await import('../dist/app.js?watch-ui');for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r));
nav.handlers.click();assert.match(app.innerHTML,/Bảng xếp hạng/);
const assertHeading=()=>{const heading=app.innerHTML.match(/<header class="page-head">[\s\S]*?<\/header>/)[0];assert.doesNotMatch(heading,/eyebrow/);assert.match(heading,/<h1>So sánh theo cơ quan<\/h1><p>[^<]+ · Tháng 10\/2026<\/p>/)};
assertHeading();tabs[0].handlers.click();for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r));assertHeading();
assert.match(app.innerHTML,/Xã, phường<\/button><button[^>]*data-agency-tab="watch"/);
assert.doesNotMatch(app.innerHTML,/>Mặc định<|Hồ sơ tiếp nhận tương đồng/);
assert.match(app.innerHTML,/Cùng hạng cân \(±20% HS\)/);
assert.equal(choices.length,0,'No full inventory displayed before keyword search');
assert.doesNotMatch(app.innerHTML,/Nhập từ khóa để tìm và chọn cơ quan\.|Danh sách được lưu cho tài khoản này trên trình duyệt đang dùng\./);
search.handlers.input({target:{value:'UBND',selectionStart:4}});
assert.equal(choices.length,7,'Only other communes; no province departments');
filter.handlers.change({target:{checked:true}});
assert.equal(choices.length,5);assert.match(app.innerHTML,/5 xã, phường cùng tỉnh phù hợp/);assert.match(app.innerHTML,/800–1\.200 hồ sơ/);
for(let i=0;i<5;i++){const c=choices[i];c.checked=true;c.handlers.change()}
assert.match(app.innerHTML,/5\/5 cơ quan/);await save.handlers.click();
assert.equal(serverIds.length,5);
assert.equal((app.innerHTML.match(/<tbody>[\s\S]*?<\/tbody>/)[0].match(/<tr/g)??[]).length,6,'Own baseline + five watched units');
assert.ok(app.innerHTML.indexOf('data-watch-save')>app.innerHTML.indexOf('</table>'),'Save below comparison table');
const stored=JSON.stringify(serverIds);
const rowNames=()=>[...app.innerHTML.match(/<tbody>[\s\S]*?<\/tbody>/)[0].matchAll(/<tr[^>]*><td>(?:<strong>)?([^<]+)/g)].map(m=>m[1]);
const selected=JSON.parse(stored).map(id=>communes.find(u=>u.departmentId===id));
for(let column=0;column<7;column++){
 sorts[column].handlers.click();
 assert.match(app.innerHTML,/aria-sort="descending"/);
 assert.deepEqual(rowNames(),[...selected,own].sort((a,b)=>communes.indexOf(b)-communes.indexOf(a)).map(u=>u.departmentName),'Descending; own agency sorted with peers');
 assert.match(app.innerHTML,/<tr class="mine"><td><strong>/,'Own agency remains highlighted');
 sorts[column].handlers.click();
 assert.match(app.innerHTML,/aria-sort="ascending"/);
 assert.deepEqual(rowNames(),[...selected,own].sort((a,b)=>communes.indexOf(a)-communes.indexOf(b)).map(u=>u.departmentName),'Ascending; own agency sorted with peers');
}
assert.equal(JSON.stringify(serverIds),stored,'Sorting never rewrites saved selections');
assert.equal(watchCalls.filter(c=>c.options.method!=='POST').length,1,'One lazy read, not on every sort or render');
assert.equal(watchCalls.filter(c=>c.options.method==='POST').length,1,'Save only on explicit click');
assert.equal(watchCalls.find(c=>c.options.method==='POST').options.headers['X-QD766-CSRF'],'test');
levels[1].handlers.click();assert.match(app.innerHTML,/Bảng xếp hạng/);
console.log('AGENCY_WATCH_UI_OK: adjacent tabs, keyword-only choices, ±20%, save below, 7 sortable columns both directions including own agency, highlight and saved selections preserved');
