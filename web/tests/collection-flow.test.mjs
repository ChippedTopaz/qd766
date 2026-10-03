import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const original=structuredClone(Object.values(data.snapshots).find(s=>s.scope==='all'));
data.periods=[{id:'month-2026-09',label:'Tháng 9/2026',type:'month',year:2026,value:9},{id:'month-2026-10',label:'Tháng 10/2026',type:'month',year:2026,value:10}];
const item={id:data.formality.id,code:data.formality.code,name:data.formality.name,available:false,executionLevels:[],field:'',publishingAgency:''};
data.snapshots={'month-2026-09:all':original,'month-2026-10:all':original,
  'month-2026-10:formality':{...original,scope:'formality',formalityId:'different-formality'}};
const root={innerHTML:''},controls=new Map(),timers=[],calls=[];
function control(id){if(!controls.has(id))controls.set(id,{value:item.id,dataset:{},handlers:{},addEventListener(kind,cb){this.handlers[kind]=cb;}});return controls.get(id);}
globalThis.document={title:'',querySelector:s=>s==='#app'?root:['#province-select','#unit-select'].includes(s)?null:s.startsWith('#')?control(s):null,
  querySelectorAll:s=>s==='input[name=catalog-formality]'?[control('radio')]:s==='[data-action=submit-statistics]'?[control('submit')]:[]};
globalThis.window={setTimeout:(callback,delay)=>timers.push({callback,delay}),clearTimeout:()=>{}};
globalThis.scrollTo=()=>{};
let finishPost;
globalThis.fetch=async(url,options)=>{
  calls.push({url,method:options?.method??'GET'});
  let body;
  if(options?.method==='POST')return new Promise(resolve=>{finishPost=()=>resolve({ok:true,json:async()=>({state:'queued',jobId:'job-1',circuitState:'open',message:'Chờ kết nối nguồn'})});});
  if(url==='/api/v1/access-policy')body={publicReadOnly:false};
  else if(url==='/api/v1/dashboard')body=data;
  else if(url==='/api/v1/dashboard/provinces')body=[];
  else if(url.includes('/province-rankings'))body=[];
  else if(url.includes('/preview?'))body={counts:{selected:1,available:0,missing:1},fields:[],items:[item]};
  else if(url.includes('/selection?'))return {ok:false,status:404};
  else if(url.includes('/collection-jobs/'))body={state:'succeeded'};
  else throw new Error('Unexpected URL '+url);
  return {ok:true,status:200,json:async()=>structuredClone(body)};
};
async function settle(){for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));}
await import('../dist/app.js');await settle();
controls.get('#scope-select').handlers.change({target:{value:'formality'}});await settle();
controls.get('radio').handlers.change();await settle();
assert(calls.some(c=>c.url.includes('/selection?')),'Wrong legacy TTHC must not be reused');
controls.get('#period-value').handlers.change({target:{value:'month-2026-09'}});await settle();
assert.equal(calls.filter(c=>c.method==='POST').length,0,'Selecting scope/TTHC/period must not create jobs');
assert.match(root.innerHTML,/Lấy dữ liệu/);
controls.get('submit').handlers.click();controls.get('submit').handlers.click();await settle();
assert.equal(calls.filter(c=>c.method==='POST').length,1,'Double click only submits once');
controls.get('#period-value').handlers.change({target:{value:'month-2026-10'}});await settle();
finishPost();await settle();
assert.equal(timers.length,1,'Blocked job is monitored even after changing period');
timers.shift().callback();await settle();
assert.match(root.innerHTML,/Tháng 9\/2026.*dữ liệu đã được lưu/i);
assert.equal(calls.filter(c=>c.method==='POST').length,1,'Polling and completion never create a new job');
console.log('COLLECTION_FLOW_OK: filter GET-only, legacy TTHC identity, explicit submit, double-click guard, blocked job and changed-period notification');
