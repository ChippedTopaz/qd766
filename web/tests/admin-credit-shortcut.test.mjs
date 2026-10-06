import assert from 'node:assert/strict';
import {installTrialCreditManager} from '../dist/trial-credit-admin.js';
const nodes=new Map();
function node(id){
 const result={id,value:'',hidden:false,disabled:false,handlers:{},textContent:'',_html:'',
  addEventListener(type,fn){this.handlers[type]=fn;},
  set innerHTML(html){this._html=html;if(id==='credit-account'){this.value=html.match(/value="([^"]+)"/)?.[1]??'';}},
  get innerHTML(){return this._html;}};
 nodes.set(id,result);return result;
}
function parse(html){for(const match of html.matchAll(/id="([^"]+)"/g))if(!nodes.has(match[1]))node(match[1]);}
const section={set innerHTML(html){parse(html);},querySelector(selector){
 if(selector==='.form-grid')return {insertAdjacentHTML(where,html){parse(html);}};
 return nodes.get(selector.slice(1));}};
globalThis.document={createElement(){return section;}};
const requests=[];let grants=0,changed=0,releaseGrant;
const users=[{id:'a',name:'A',email:null,active:true,admitted:true,canCollect:true,credits:100,reservedCredits:0,walletMode:'sources'},
 {id:'b',name:'B',email:null,active:true,admitted:true,canCollect:true,credits:100,reservedCredits:0,walletMode:'sources'}];
const api=async(path,body)=>{requests.push({path,body});
 if(path==='access-policy')return {trialCreditManagement:true,defaultCollectionAccess:true};
 if(path==='admin/accounts')return users;
 if(path.endsWith('/credits'))return {availableCredits:100,reservedCredits:0,items:[]};
 if(path.endsWith('/trial-credit')){grants++;await new Promise(resolve=>{releaseGrant=resolve;});return {};}
 throw new Error('Unexpected path '+path);
};
const manager=await installTrialCreditManager({append(){}},api,async()=>{changed++;});
await manager.openAccount('b');
assert.equal(nodes.get('credit-account').value,'b');
assert.equal(nodes.get('credit-amount').value,'0');
assert.equal(grants,0,'Opening shortcut must not grant credit');
assert.equal(requests.at(-1).path,'admin/accounts/b/credits');
nodes.get('credit-amount').value='30';nodes.get('credit-source').value='purchased';nodes.get('credit-reason').value='Test grant';
const submit=()=>nodes.get('credit-form').handlers.submit({preventDefault(){}});
submit();submit();
await new Promise(resolve=>setImmediate(resolve));
assert.equal(grants,1,'Double submit creates one request');
assert.equal(requests.find(r=>r.body)?.path,'admin/accounts/b/trial-credit');
assert.equal(requests.find(r=>r.body)?.body.amount,30);
await assert.rejects(()=>manager.openAccount('a'),/chờ giao dịch/);
releaseGrant();for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
assert.equal(changed,1);assert.equal(nodes.get('credit-account').value,'b');
assert.equal(nodes.get('credit-save').disabled,false);
await assert.rejects(()=>manager.openAccount('unknown'),/chưa hoạt động/);
assert.equal(nodes.get('credit-account').value,'b');
console.log('ADMIN_CREDIT_SHORTCUT_OK: correct target, no implicit grant, one POST, source preserved, refresh after success');
