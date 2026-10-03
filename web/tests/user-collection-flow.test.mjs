import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const original=structuredClone(Object.values(data.snapshots).find(s=>s.scope==='all'));
data.periods=[{id:'month-2026-10',label:'Tháng 10/2026',type:'month',year:2026,value:10}];
const item={id:data.formality.id,code:data.formality.code,name:data.formality.name,available:false,executionLevels:[],field:'Lĩnh vực thử',publishingAgency:''};
data.snapshots={'month-2026-10:all':original,'month-2026-10:formality':{...original,scope:'formality',formalityId:'different-formality'}};
const root={innerHTML:''},controls=new Map(),calls=[],urls=[];
function control(id){if(!controls.has(id))controls.set(id,{value:item.id,dataset:{},handlers:{},addEventListener(kind,cb){this.handlers[kind]=cb;}});return controls.get(id);}
globalThis.document={title:'',querySelector:s=>s==='#app'?root:['#province-select','#unit-select','#catalog-field'].includes(s)?null:s.startsWith('#')||s.startsWith('[data-action=')?control(s):null,
  querySelectorAll:s=>s==='input[name=catalog-formality]'?[control('radio')]:s==='[data-action=submit-statistics]'?[control('submit')]:s==='[data-action=new-collection]'?[control('new')]:[]};
globalThis.TomSelect=class{constructor(){this.control_input={}}on(){}destroy(){}};
globalThis.window={setTimeout:()=>1,clearTimeout:()=>{}};
globalThis.location={pathname:'/',search:process.argv.includes('--restore')?`?period=month-2026-10&scope=formality&formality=${item.id}`:''};
globalThis.history={replaceState:(_,__,url)=>urls.push(url)};globalThis.scrollTo=()=>{};
let owned=process.argv.includes('--restore'),rows=[],finishConfirmation;
globalThis.fetch=async(url,options)=>{
  calls.push({url,method:options?.method??'GET',options});let body;
  if(url==='/api/v1/access-policy')body={publicReadOnly:true,paidRequestsEnabled:true,loginRequired:true,googleLoginEnabled:true};
  else if(url==='/api/v1/auth/me')body={name:'Tester',provinceId:data.province.id,csrfToken:'test-csrf',credits:10};
  else if(url==='/api/v1/dashboard')body=data;
  else if(url==='/api/v1/dashboard/provinces')body=[];
  else if(url.includes('/province-rankings'))body=[];
  else if(url.includes('/preview?'))body={counts:{selected:1,available:0,missing:1},fields:['Lĩnh vực thử'],items:[item]};
  else if(url.startsWith('/api/v1/me/formalities?'))body={items:owned?[item]:[]};
  else if(url==='/api/v1/me/collection-quote')body={quote:'signed-quote',items:[{...item,cost:3,owned:false}],totalCredits:3,availableCredits:10};
  else if(url==='/api/v1/me/formality-requests'&&options?.method==='POST')return new Promise(resolve=>{finishConfirmation=()=>{owned=true;rows=[{id:'request-1',state:'ready',formalityId:item.id,code:item.code,name:item.name,periodType:'month',year:2026,periodValue:10,creditCost:3,createdAt:'2026-10-03',error:null}];resolve({ok:true,json:async()=>({items:rows,availableCredits:7})});};});
  else if(url==='/api/v1/me/formality-requests')body={items:rows,availableCredits:10};
  else if(url.includes('/selection?'))body={snapshot:{...original,scope:'formality',formalityId:item.id},metadata:{detailsAvailable:true,capturedAt:'2026-10-03T00:00:00Z'}};
  else throw new Error('Unexpected URL '+url);
  return {ok:true,status:200,json:async()=>structuredClone(body)};
};
async function settle(){for(let i=0;i<10;i++)await new Promise(resolve=>setImmediate(resolve));}
await import('../dist/app.js');await settle();
if(process.argv.includes('--restore')){
  assert(calls.some(c=>c.url.includes('/selection?')));assert.match(root.innerHTML,/Thủ tục đã khai thác/);
  assert.equal(calls.filter(c=>c.method==='POST').length,0);console.log('COLLECTION_RESTORE_OK: saved period/TTHC via own library, GET-only');
}else{
  controls.get('#scope-select').handlers.change({target:{value:'formality'}});await settle();
  assert.match(root.innerHTML,/Thủ tục đã khai thác/);assert.doesNotMatch(root.innerHTML,/catalog-list/);
  controls.get('new').handlers.click();await settle();assert.match(root.innerHTML,/Khai thác dữ liệu TTHC/);
  controls.get('radio').handlers.change();await settle();assert.equal(calls.filter(c=>c.method==='POST').length,0);
  controls.get('submit').handlers.click();await settle();assert.match(root.innerHTML,/3 credit/);
  assert.equal(calls.filter(c=>c.url==='/api/v1/me/formality-requests'&&c.method==='POST').length,0);
  controls.get('[data-action=confirm-collection]').handlers.click();controls.get('[data-action=confirm-collection]').handlers.click();await settle();
  assert.equal(calls.filter(c=>c.url==='/api/v1/me/formality-requests'&&c.method==='POST').length,1);
  finishConfirmation();await settle();assert.match(root.innerHTML,/Yêu cầu của tôi/);assert.match(root.innerHTML,/Xem dữ liệu/);
  controls.get('#saved-formality').handlers.change({target:{value:item.id}});await settle();
  assert(calls.some(c=>c.url.includes('/selection?')));assert(urls.at(-1).includes('scope=formality'));
  assert.doesNotMatch(root.innerHTML,/class="formality-notice|period-notice success/);
  assert(calls.every(c=>!c.url.includes('/dashboard/requests')&&!c.url.includes('/collection-jobs')));
  console.log('COLLECTION_FLOW_OK: own library, explicit quote/confirmation, double-click, history, GET-only reuse');
}
