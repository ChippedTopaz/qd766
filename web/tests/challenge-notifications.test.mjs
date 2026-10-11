import assert from 'node:assert/strict';
import {bindChallengeNotifications} from '../dist/challenges.js';
const pending={id:'one',senderId:'a',recipientId:'b',sender:'Người A',recipient:'B',senderUnit:'Xã A',recipientUnit:'Xã B',periodType:'month',year:2027,periodValue:11,state:'pending',senderScore:null,recipientScore:null,winnerId:null,canAnswer:true};
let host=null,dialog=null,posted=false,requests=[],timer;
const button={insertAdjacentHTML(position,html){assert.equal(position,'beforebegin');assert.match(html,/data-challenge-notifications/);host={hidden:false,innerHTML:'',querySelector(){return null},querySelectorAll(s){if(s==='button')return [];const controls=['accept','decline'].map(action=>({dataset:{incomingId:'one',incomingAction:action},addEventListener(k,fn){this[k]=fn}}));host.controls=controls;return controls}}}};
globalThis.document={hidden:false,querySelector(s){return s==='[data-challenge-board]'?button:s==='[data-challenge-notifications]'?host:s==='.challenge-confirm'?dialog:null},
 body:{append(d){dialog=d}},createElement(){
  const events={},buttons=new Map();
  return {innerHTML:'',setAttribute(){},showModal(){},remove(){dialog=null},querySelector(s){if(!buttons.has(s))buttons.set(s,{addEventListener(k,fn){this[k]=fn}});return buttons.get(s)},addEventListener(k,fn){events[k]=fn},close(){events.close()}}
 }};
globalThis.window={setTimeout(fn,ms){assert.equal(ms,30000);timer=fn;return 1},clearTimeout(){},confirm(){throw Error('Browser confirm forbidden')}};
globalThis.fetch=async(url,options)=>{
 requests.push({url,options});
 if(options.method==='POST'){posted=true;return {ok:true,json:async()=>({state:'accepted'})}}
 return {ok:true,json:async()=>({count:posted?0:1,items:posted?[]:[pending]})};
};
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r))};
bindChallengeNotifications('account-b:province','csrf-b',()=>{});await settle();
assert.equal(host.hidden,false);assert.match(host.innerHTML,/Người A/);
const first=host.controls[0].click();await host.controls[0].click();
assert.equal(requests.filter(r=>r.options.method==='POST').length,0,'Wait for custom confirmation');
assert.match(dialog.innerHTML,/Chấp nhận thách đấu/);
dialog.querySelector('[data-confirm-ok]').click();await first;await settle();
assert.equal(requests.filter(r=>r.options.method==='POST').length,1);
assert.equal(requests.find(r=>r.options.method==='POST').options.headers['X-QD766-CSRF'],'csrf-b');
assert.equal(host.hidden,true);
const before=requests.length;document.hidden=true;timer();await settle();assert.equal(requests.length,before,'Hidden tabs do not poll');
document.hidden=false;timer();await settle();assert.equal(requests.length,before+1);
assert.ok(requests.every(r=>r.url.startsWith('/api/v1/me/challenges')));
console.log('CHALLENGE_NOTIFICATIONS_OK: above BXH, recipient card, styled confirmation, one CSRF answer, removed after acceptance, 30s visible-tab polling only');
