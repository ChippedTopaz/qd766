import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const original=structuredClone(Object.values(data.snapshots).find(s=>s.scope==='all'));
original.delivery={result:'detail',capturedAt:'2026-10-03T00:00:00Z',detailsCapturedAt:'2026-10-03T00:00:00Z',detailsAvailable:true,stale:true,message:'Đang sử dụng dữ liệu gần nhất.'};
data.periods=[{id:'month-2026-10',label:'Tháng 10/2026',type:'month',year:2026,value:10}];
const item={id:data.formality.id,code:data.formality.code,name:data.formality.name,available:false,executionLevels:[],field:'Lĩnh vực thử',publishingAgency:''};
data.snapshots={'month-2026-10:all':original,'month-2026-10:formality':{...original,scope:'formality',formalityId:'different-formality'}};
const compactRestore=process.argv.includes('--compact-restore');
if(compactRestore)data.snapshots['month-2026-10:all']={...original,detailsLoaded:false,datasets:original.datasets.map(d=>({...d,root:{...d.root,metrics:[]},children:d.children.map(c=>({...c,metrics:[]}))}))};
const root={innerHTML:'',setAttribute(){},querySelector(){return null}},controls=new Map(),calls=[],urls=[];
function control(id){if(!controls.has(id))controls.set(id,{id:id.replace(/^#/,''),value:item.id,dataset:{},handlers:{},selectionStart:2,selectionEnd:2,selectionDirection:'none',focus(){document.activeElement=this;this.focusCount=(this.focusCount??0)+1;},setSelectionRange(start,end,direction){this.selectionStart=start;this.selectionEnd=end;this.selectionDirection=direction;},addEventListener(kind,cb){this.handlers[kind]=cb;}});return controls.get(id);}
globalThis.document={title:'',getElementById:id=>control('#'+id),querySelector:s=>s==='#app'?root:['#province-select','#unit-select','#catalog-field'].includes(s)?null:s.startsWith('#')||s.startsWith('[data-action=')?control(s):null,
  querySelectorAll:s=>s==='[data-nav]'?[control('overview')]:s==='input[name=catalog-formality]'?[control('radio')]:s==='[data-action=submit-statistics]'?[control('submit')]:s==='[data-action=new-collection]'?[control('new')]:[]};
control('overview').dataset.nav='overview';
globalThis.TomSelect=class{constructor(){this.control_input={}}on(){}destroy(){}};
const timers=new Map();let timerId=0;
globalThis.window={setTimeout:(cb,delay)=>{timers.set(++timerId,{cb,delay});return timerId;},clearTimeout:id=>timers.delete(id)};
globalThis.location={pathname:'/',hash:'',search:process.argv.includes('--restore')?`?period=month-2026-10&scope=formality&formality=${item.id}`:''};
globalThis.history={replaceState:(_,__,url)=>urls.push(url)};globalThis.scrollTo=()=>{};
let owned=process.argv.includes('--restore'),rows=[],finishConfirmation;
globalThis.fetch=async(url,options)=>{
  calls.push({url,method:options?.method??'GET',options});let body;
  if(url==='/api/v1/access-policy')body={publicReadOnly:true,paidRequestsEnabled:true,loginRequired:true,googleLoginEnabled:true};
  else if(url==='/api/v1/auth/me')body={name:'Tester',provinceId:data.province.id,csrfToken:'test-csrf',credits:10,canCollect:true};
  else if(url==='/api/v1/dashboard?fast=true&compact=true')body=data;
  else if(url==='/api/v1/dashboard/provinces')body=[];
  else if(url.includes('/province-rankings'))body=[];
  else if(url.includes('/preview?'))body={counts:{selected:1,available:0,missing:1},fields:['Lĩnh vực thử'],items:[item]};
  else if(url.startsWith('/api/v1/me/formalities?')){
    assert.equal(new URL(url,'https://example.test').searchParams.get('root_department_id'),data.province.id);
    body={items:owned?[item]:[]};
  }
  else if(url==='/api/v1/me/collection-quote'){
    assert.equal(JSON.parse(options.body).rootDepartmentId,data.province.id);
    body={quote:'signed-quote',items:[{...item,cost:3,owned:false}],totalCredits:3,availableCredits:10};
  }
  else if(url==='/api/v1/me/formality-requests'&&options?.method==='POST')return new Promise(resolve=>{finishConfirmation=()=>{owned=true;rows=[{id:'request-1',state:'ready',formalityId:item.id,code:item.code,name:item.name,periodType:'month',year:2026,periodValue:10,creditCost:3,createdAt:'2026-10-03',error:null}];resolve({ok:true,json:async()=>({items:rows,availableCredits:7})});};});
  else if(url.startsWith('/api/v1/me/formality-requests?')){
    assert.equal(new URL(url,'https://example.test').searchParams.get('root_department_id'),data.province.id);
    body={items:rows,availableCredits:10};
  }
  else if(url.includes('/selection?'))body={snapshot:compactRestore?original:{...original,scope:'formality',formalityId:item.id},metadata:{detailsAvailable:true,capturedAt:'2026-10-03T00:00:00Z'}};
  else throw new Error('Unexpected URL '+url);
  return {ok:true,status:200,json:async()=>structuredClone(body)};
};
async function settle(){for(let i=0;i<10;i++)await new Promise(resolve=>setImmediate(resolve));}
await import('../dist/app.js');await settle();
assert.doesNotMatch(root.innerHTML,/Không thể tải dữ liệu/);
if(compactRestore){
  assert(calls.some(c=>c.url.includes('/selection?')&&c.url.includes('scope=all')));
  assert.equal(calls.filter(c=>c.method==='POST').length,0);
  assert.doesNotMatch(root.innerHTML,/Không thể tải dữ liệu/);
  console.log('COMPACT_RESTORE_OK: historical detail loaded via GET, no collection request');
}else if(process.argv.includes('--restore')){
  assert(calls.some(c=>c.url.includes('/selection?')));assert.match(root.innerHTML,/Thủ tục đã khai thác/);
  assert.equal(calls.filter(c=>c.method==='POST').length,0);console.log('COLLECTION_RESTORE_OK: saved period/TTHC via own library, GET-only');
}else{
  controls.get('new').handlers.click();await settle();
  const initialNotes=root.innerHTML.match(/<details class="comparison-notes">[\s\S]*?<\/details>/)?.[0];
  assert(initialNotes,'Collection data caveats must be collapsed, not displayed as banners');
  assert.match(initialNotes,/Chưa cập nhật được/);
  assert.doesNotMatch(root.innerHTML.replace(initialNotes,''),/Chưa cập nhật được|Số liệu tạm thời|Hai thời điểm cập nhật/);
  controls.get('overview').handlers.click();await settle();
  controls.get('#scope-select').handlers.change({target:{value:'formality'}});await settle();
  assert.match(root.innerHTML,/Thủ tục đã khai thác/);assert.doesNotMatch(root.innerHTML,/catalog-list/);
  assert.match(root.innerHTML,/Đang online: <strong data-online-count>/);
  assert.match(root.innerHTML,/<div class="context-bottom"><label class="field saved-formality">/);
  controls.get('new').handlers.click();await settle();assert.match(root.innerHTML,/Khai thác dữ liệu TTHC/);
  const query=control('#catalog-query');query.value='đất';document.activeElement=query;
  query.handlers.input({target:query});
  const searchTimer=[...timers.values()].find(timer=>timer.delay===350);assert(searchTimer);searchTimer.cb();await settle();
  assert.equal(document.activeElement,query);assert(query.focusCount>=2);assert.equal(query.selectionStart,2);assert.equal(query.selectionEnd,2);
  assert.match(root.innerHTML,/value="đất"/);
  document.activeElement=null;
  controls.get('radio').handlers.change();await settle();assert.equal(calls.filter(c=>c.method==='POST').length,0);
  controls.get('submit').handlers.click();await settle();assert.match(root.innerHTML,/3 Credit/);
  assert.equal(calls.filter(c=>c.url==='/api/v1/me/formality-requests'&&c.method==='POST').length,0);
  controls.get('[data-action=confirm-collection]').handlers.click();controls.get('[data-action=confirm-collection]').handlers.click();await settle();
  assert.equal(calls.filter(c=>c.url==='/api/v1/me/formality-requests'&&c.method==='POST').length,1);
  finishConfirmation();await settle();assert.match(root.innerHTML,/Lịch sử tra cứu/);assert.match(root.innerHTML,/Xem dữ liệu/);
  controls.get('#saved-formality').handlers.change({target:{value:item.id}});await settle();
  assert(calls.some(c=>c.url.includes('/selection?')));assert(urls.at(-1).includes('scope=formality'));
  assert.doesNotMatch(root.innerHTML,/class="formality-notice|period-notice success/);
  assert(calls.every(c=>!c.url.includes('/dashboard/requests')&&!c.url.includes('/collection-jobs')));
  console.log('COLLECTION_FLOW_OK: own library, explicit quote/confirmation, double-click, history, GET-only reuse');
}
