import assert from 'node:assert/strict';
import {installTrialCreditManager} from '../dist/trial-credit-admin.js';

const nodes=new Map();
function parse(html){
  for(const m of html.matchAll(/id="([^"]+)"/g))if(!nodes.has(m[1])){
    const id=m[1];nodes.set(id,{value:'',disabled:false,hidden:false,textContent:'',handlers:{},
      addEventListener(type,handler){this.handlers[type]=handler;},
      insertAdjacentHTML(where,html){parse(html);},
      set innerHTML(html){this.html=html;if(id==='credit-account')this.value=html.match(/value="([^"]+)"/)?.[1]??'';},
      get innerHTML(){return this.html??'';}});
  }
}
const section={set innerHTML(html){parse(html);},querySelector(selector){
  return selector==='.form-grid'?{insertAdjacentHTML(where,html){parse(html);}}:nodes.get(selector.slice(1));
}};
globalThis.document={createElement(){return section;}};
const users=Array.from({length:510},(_,i)=>({id:String(i),name:`User ${i}`,email:`user${i}@example.test`,active:true,admitted:true,
  canCollect:true,credits:85,reservedCredits:0,walletMode:'sources'}));
const requests=[];let slowResolve;
const api=async(path,body)=>{
  requests.push({path,body});assert.equal(body,undefined,'Browsing/searching must never grant Credit');
  if(path==='access-policy')return {trialCreditManagement:true,defaultCollectionAccess:true};
  if(path.endsWith('/credits'))return {availableCredits:85,reservedCredits:0,items:[]};
  if(path.startsWith('admin/accounts?')){
    const q=new URLSearchParams(path.split('?')[1]);
    if(q.get('search')==='slow')return new Promise(resolve=>{slowResolve=resolve;});
    const filtered=users.filter(a=>(!q.has('accountId')||a.id===q.get('accountId'))&&
      (!q.get('search')||a.email===q.get('search')));
    const page=Number(q.get('page')),start=(page-1)*10;
    return {items:filtered.slice(start,start+10),total:filtered.length,page,pageSize:10};
  }
  throw new Error('Unexpected '+path);
};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const settle=async()=>{for(let i=0;i<5;i++)await tick();};
const manager=await installTrialCreditManager({append(){}},api);
assert.equal(nodes.get('credit-page').textContent,'Trang 1/51 · 510 tài khoản');
assert.equal((nodes.get('credit-account').innerHTML.match(/<option /g)||[]).length,10);
assert.equal(nodes.get('credit-prev').disabled,true);assert.equal(nodes.get('credit-next').disabled,false);
nodes.get('credit-next').handlers.click();await settle();
assert.equal(nodes.get('credit-account').value,'10');assert.equal(nodes.get('credit-page').textContent,'Trang 2/51 · 510 tài khoản');
await manager.openAccount('509');
assert.equal(nodes.get('credit-account').value,'509','Shortcut finds account beyond former cap');
assert.equal(nodes.get('credit-search').value,'user509@example.test');
assert.equal(nodes.get('credit-source-label').hidden,false,'Wallet source selector retained');
assert.equal(requests.at(-1).path,'admin/accounts/509/credits');
assert.ok(requests.some(r=>r.path==='admin/accounts?page=1&accountId=509'));

nodes.get('credit-search').value='user508@example.test';nodes.get('credit-search').handlers.input();
assert.equal(nodes.get('credit-save').disabled,true,'Cannot grant stale selection while search is pending');
await new Promise(resolve=>setTimeout(resolve,280));await settle();
assert.equal(nodes.get('credit-account').value,'508');
assert.ok(requests.some(r=>r.path==='admin/accounts?page=1&status=active&search=user508%40example.test'));

// A slow prior search cannot overwrite a newer shortcut result.
nodes.get('credit-search').value='slow';nodes.get('credit-search').handlers.input();
await new Promise(resolve=>setTimeout(resolve,280));
await manager.openAccount('509');
slowResolve({items:[users[0]],total:1,page:1,pageSize:10});await settle();
assert.equal(nodes.get('credit-account').value,'509');assert.equal(nodes.get('credit-save').disabled,false);

users[509].active=false;
await assert.rejects(()=>manager.openAccount('509'),/chưa hoạt động hoặc chưa được duyệt/);
assert.equal(nodes.get('credit-account').value,'');assert.equal(nodes.get('credit-save').disabled,true);
nodes.get('credit-form').handlers.submit({preventDefault(){}});await settle();
users[509].active=true;users[509].admitted=false;
await assert.rejects(()=>manager.openAccount('509'),/chưa hoạt động hoặc chưa được duyệt/);
await assert.rejects(()=>manager.openAccount('missing'),/Không tìm thấy tài khoản/);
assert.equal(nodes.get('credit-save').disabled,true);
assert.ok(requests.every(r=>!r.body&&!r.path.endsWith('/trial-credit')));
console.log('ADMIN_CREDIT_PAGINATION_PASS: 510 accounts, 10/page, exact shortcut, global email search, source retained, stale response guard, real status checks, no credit writes');
