import assert from 'node:assert/strict';
import {personalCreditMarkup,CREDIT_PAGE_SIZE} from '../dist/personal-credit-view.js';
import {openPersonalCredits} from '../dist/personal-credits.js';
const wallet={accessTier:'agency',role:'user',walletMode:'sources',availableCredits:85,reservedCredits:0,subscriptionCredits:85,purchasedCredits:300,
 subscriptionEndsAt:'2026-11-04T03:16:05Z',subscriptionState:'active',canRedeem:true,redemptionCost:300,total:31,items:[]};
const entry=i=>({type:i%2?'reserve':'charge',source:'purchased',amount:5,availableDelta:-5,reservedDelta:0,availableAfter:85,reservedAfter:0,at:'2026-10-11T08:00:00Z'});
wallet.items=Array.from({length:31},(_,i)=>entry(i));
assert.equal(CREDIT_PAGE_SIZE,15);
const general=personalCreditMarkup(wallet,'general',0);
assert.match(general,/Loại tài khoản: <strong>Cơ quan/);assert.match(general,/Subscription đến/);assert.doesNotMatch(general,/mua|bán|tiền|chi phí/i);
assert.doesNotMatch(general,/<table/);assert.match(general,/data-credit-tab="general"/);
const history=personalCreditMarkup(wallet,'history',0);
assert.equal((history.match(/<tbody>[\s\S]*?<\/tbody>/)[0].match(/<tr>/g)||[]).length,15);
assert.match(history,/Trang 1\/3/);assert.match(history,/data-prev disabled/);assert.doesNotMatch(history,/mua|bán|tiền|chi phí/i);
assert.match(personalCreditMarkup({...wallet,total:0,items:[]},'history',0),/Chưa có giao dịch/);
let current,requests=[],renewals=0,balanceUpdate,held;
const oldFocus={isConnected:true,focus(){this.restored=true}};
function dialog(){
 const events={},controls=new Map();let html='';
 const d={isConnected:false,className:'',get innerHTML(){return html},set innerHTML(v){html=v;controls.clear()},setAttribute(){},showModal(){},remove(){this.isConnected=false},close(){events.close?.()},addEventListener(k,cb){events[k]=cb},querySelector(s){
  const attr=s.slice(1,-1);if(!html.includes(attr))return null;
  if(!controls.has(s))controls.set(s,{isConnected:true,textContent:'',hidden:true,disabled:new RegExp(attr+'(?:>| disabled)').test(html)&&html.includes(attr+' disabled'),handlers:{},addEventListener(k,cb){this.handlers[k]=cb}});
  return controls.get(s);
 },querySelectorAll(s){if(s!=='[data-credit-tab]')return [];return ['general','history'].map(tab=>{
  const key='tab-'+tab;if(!controls.has(key))controls.set(key,{dataset:{creditTab:tab},handlers:{},addEventListener(k,cb){this.handlers[k]=cb}});return controls.get(key);
 })}};return d;
}
globalThis.document={activeElement:oldFocus,querySelector:()=>current?.isConnected?current:null,createElement:()=>dialog(),body:{append(d){current=d;d.isConnected=true}}};
globalThis.fetch=async(url,options={})=>{
 requests.push({url,options});
 if(url==='/api/v1/auth/me')return {ok:true,json:async()=>({csrfToken:'csrf'})};
 if(url==='/api/v1/me/subscription/redemption'){renewals++;assert.equal(options.headers['X-QD766-CSRF'],'csrf');assert.equal(JSON.parse(options.body).expectedCost,300);return {ok:true,json:async()=>({availableCredits:12})}}
 const query=new URL(url,'https://test.local').searchParams,offset=Number(query.get('offset'));assert.equal(query.get('limit'),'15');
 if(held){const pending=held;held=null;await pending}
 return {ok:true,json:async()=>({...wallet,items:wallet.items.slice(offset,offset+15)})};
};
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r))};
const tab=id=>current.querySelectorAll('[data-credit-tab]').find(c=>c.dataset.creditTab===id).handlers.click();
openPersonalCredits((a,r)=>balanceUpdate=[a,r]);await settle();assert.match(current.innerHTML,/Loại tài khoản/);assert.equal(requests.length,1);
tab('history');assert.equal(requests.length,1,'Switching tabs uses current response, no new read');
assert.match(current.innerHTML,/Trang 1\/3/);
const next=current.querySelector('[data-next]');next.handlers.click();next.handlers.click();await settle();
assert.equal(requests.length,2,'Double-click page guard');assert.match(requests.at(-1).url,/offset=15&limit=15/);assert.match(current.innerHTML,/Trang 2\/3/);
current.querySelector('[data-next]').handlers.click();await settle();assert.match(requests.at(-1).url,/offset=30&limit=15/);assert.match(current.innerHTML,/Trang 3\/3/);
assert.equal((current.innerHTML.match(/<tbody>[\s\S]*?<\/tbody>/)[0].match(/<tr>/g)||[]).length,1);
tab('general');assert.doesNotMatch(current.innerHTML,/<table/);assert.equal(requests.length,3);
current.querySelector('[data-renew]').handlers.click();assert.equal(current.querySelector('[data-renew-confirm]').hidden,false);
current.querySelector('[data-cancel-renew]').handlers.click();assert.equal(current.querySelector('[data-renew-confirm]').hidden,true);assert.equal(renewals,0);
const confirm=current.querySelector('[data-confirm-renew]');const event={currentTarget:confirm};
const p=confirm.handlers.click(event);await confirm.handlers.click(event);await p;
assert.equal(renewals,1,'One confirmed renewal only');assert.deepEqual(balanceUpdate,[12,0]);
assert.match(current.querySelector('[data-renew-status]').textContent,/Gia hạn thành công/);
tab('history');current.querySelector('[data-prev]').handlers.click();assert.equal(requests.at(-1).url.includes('offset=0'),true,'Boundary click makes no request');
current.close();assert.equal(current.isConnected,false);assert.equal(oldFocus.restored,true);
console.log('PERSONAL_CREDIT_TABS_PASS: neutral compact overview, account tier, 15/page, tab cache, double-click guard, confirmed renewal/CSRF and balance callback retained');
