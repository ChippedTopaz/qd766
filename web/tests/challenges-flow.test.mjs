import assert from 'node:assert/strict';
import {challengeMarkup,bindChallenges} from '../dist/challenges.js';
const controls=new Map();let html='',requests=[],rows=[],allowed=true;
const selector=(name)=>{if(!html.includes(name.slice(1,-1)))return null;if(!controls.has(name))controls.set(name,{handlers:{},addEventListener(k,cb){this.handlers[k]=cb},focus(){},setSelectionRange(){}});return controls.get(name)};
globalThis.document={querySelector:selector,querySelectorAll(s){if(s==='[data-duel-agency]'&&html.includes('data-duel-agency')){const c=selector(s);c.dataset={duelAgency:'agency-b'};return [c]}if(s==='[data-duel-page]')return [...html.matchAll(/data-duel-page="(\d+)"\s*(disabled)?/g)].map(m=>{const key='page-'+m[1];if(!controls.has(key))controls.set(key,{dataset:{duelPage:m[1]},disabled:!!m[2],handlers:{},addEventListener(k,cb){this.handlers[k]=cb}});return controls.get(key)});return []}};
globalThis.window={confirm:()=>{throw new Error('Native browser confirm must not be used')}};
globalThis.document.body={append(){}};
globalThis.document.createElement=()=>{
 const buttons=new Map(),events={};
 const dialog={innerHTML:'',setAttribute(){},remove(){},querySelector(s){if(!buttons.has(s))buttons.set(s,{addEventListener(k,cb){this[k]=cb}});return buttons.get(s)},
  addEventListener(k,cb){events[k]=cb},close(){events.close?.()},showModal(){assert.doesNotMatch(this.innerHTML,/Không sử dụng Credit/);setImmediate(()=>buttons.get(allowed?'[data-confirm-ok]':'[data-confirm-cancel]').click())}};
 return dialog;
};
globalThis.fetch=async(url,options)=>{
 requests.push({url,options});
 if(options.method==='POST'){rows=[{id:'one',senderId:'a',recipientId:'b',sender:'A',recipient:'B',senderUnit:'Xã A',recipientUnit:'Xã B',periodType:'month',year:2027,periodValue:11,state:'pending',senderScore:null,recipientScore:null,winnerId:null,canAnswer:false}];return {ok:true,json:async()=>rows[0]}}
 return {ok:true,json:async()=>url.endsWith('/directory')?{eligible:true,agencies:[{id:'agency-b',name:'Xã B',users:[{id:'b',name:'Người B'}]}]}:{items:rows,page:Number(new URL(url,'https://test.local').searchParams.get('page')??1),total:rows.length?21:0,pageSize:10}};
};
const render=()=>{html=challengeMarkup();controls.clear();bindChallenges('account-a:province','csrf-secret',render)};
render();for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r));
assert.equal(requests.length,2);assert.ok(requests.every(r=>!r.options.method),'No automatic send');
selector('[data-duel-search]').handlers.input({target:{value:'Xã',selectionStart:2}});
selector('[data-duel-agency]').handlers.click();
assert.match(html,/data-duel-search[^>]*value="Xã B"/);
assert.doesNotMatch(html,/challenge-selected-agency/);
selector('[data-duel-recipient]').handlers.change({target:{value:'b'}});
assert.match(html,/<option value="b" selected>Người B<\/option>/);
assert.doesNotMatch(html,/challenge-selected-agency/);
selector('[data-duel-year]').handlers.change({target:{value:2027}});
selector('[data-duel-value]').handlers.change({target:{value:11}});
allowed=false;await selector('[data-duel-form]').handlers.submit({preventDefault(){}});
assert.equal(requests.filter(r=>r.options.method==='POST').length,0);
allowed=true;const pending=selector('[data-duel-form]').handlers.submit({preventDefault(){}});
await selector('[data-duel-form]').handlers.submit({preventDefault(){}});await pending;
const posts=requests.filter(r=>r.options.method==='POST');assert.equal(posts.length,1,'Double click guard');
assert.equal(posts[0].options.headers['X-QD766-CSRF'],'csrf-secret');
assert.deepEqual(JSON.parse(posts[0].options.body),{recipientId:'b',periodType:'month',year:2027,periodValue:11});
assert.match(html,/Đã gửi thách đấu/);assert.match(html,/Người B|Xã B/);
assert.match(html,/Trang 1\/3 · 21 kèo/);
const beforePage=requests.length;await controls.get('page-2').handlers.click();
assert.equal(requests.length,beforePage+1,'Page change does not reload directory');
assert.match(requests.at(-1).url,/\?page=2$/);assert.match(html,/Trang 2\/3/);
assert.ok(requests.every(r=>r.url.startsWith('/api/v1/me/challenges')),'No collection or Credit APIs');
selector('[data-duel-search]').handlers.input({target:{value:'Xã khác'}});
assert.match(html,/data-duel-recipient required[^>]*disabled/,'Editing agency clears the old recipient');
console.log('CHALLENGE_FLOW_OK: lazy authenticated reads, agency/person selection, future period, confirmation, one CSRF POST, no collection/Credit calls');
