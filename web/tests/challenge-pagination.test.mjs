import assert from 'node:assert/strict';
import {challengePagination,openChallengeBoard} from '../dist/challenges.js';
assert.equal(challengePagination(1,0,'data-board-page'),'');
assert.match(challengePagination(1,21,'data-board-page'),/Trang 1\/3 · 21 kèo/);
assert.match(challengePagination(1,21,'data-board-page'),/data-board-page="0" disabled/);
assert.match(challengePagination(3,21,'data-board-page'),/data-board-page="4" disabled/);
let current,requests=[],deferred;
const content={innerHTML:'',querySelectorAll(selector){
 const attr=selector.slice(1,-1),dataset=attr==='data-board-tab'?'boardTab':'boardPage';
 return [...this.innerHTML.matchAll(new RegExp(attr+'="([^"]+)"\\s*(disabled)?','g'))].map(m=>({dataset:{[dataset]:m[1]},disabled:!!m[2],addEventListener(k,cb){this[k]=cb}}));
}};
let controls=[];
const original=content.querySelectorAll;content.querySelectorAll=function(s){const result=original.call(this,s);controls=controls.filter(x=>!x.dataset[s==='[data-board-tab]'?'boardTab':'boardPage']).concat(result);return result};
globalThis.document={activeElement:null,querySelector:()=>current?.isConnected?current:null,body:{append(d){current=d;d.isConnected=true}},createElement(){
 const events={};return {innerHTML:'',setAttribute(){},showModal(){},querySelector(s){return s==='[data-board-content]'?content:{addEventListener(){}}},addEventListener(k,cb){events[k]=cb},close(){events.close()},remove(){this.isConnected=false}};
}};
globalThis.fetch=async url=>{
 requests.push(url);const u=new URL(url,'https://test.local'),status=u.searchParams.get('status'),page=Number(u.searchParams.get('page'));
 if(deferred){const pending=deferred;deferred=null;await pending}
 return {ok:true,json:async()=>({items:[],page,total:status==='active'?23:11,pageSize:10,players:[{rank:1,name:'Winner',points:9,wins:3,draws:0,losses:0}]})};
};
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r))};
const click=(key,value)=>controls.find(x=>x.dataset[key]===value).click();
await openChallengeBoard();assert.match(requests.at(-1),/status=active&page=1/);assert.match(content.innerHTML,/Trang 1\/3/);
click('boardPage','2');await settle();assert.match(content.innerHTML,/Trang 2\/3/);
click('boardTab','finished');await settle();assert.match(requests.at(-1),/status=finished&page=1/);assert.match(content.innerHTML,/Trang 1\/2/);
click('boardPage','2');await settle();assert.match(content.innerHTML,/Trang 2\/2/);
click('boardTab','active');await settle();assert.match(requests.at(-1),/status=active&page=2/,'Tabs remember independent pages');
click('boardTab','top');await settle();assert.match(content.innerHTML,/Top 20/);assert.doesNotMatch(content.innerHTML,/data-board-page/);
let resolve;deferred=new Promise(r=>resolve=r);click('boardTab','active');click('boardTab','finished');await settle();resolve();await settle();
assert.match(content.innerHTML,/Trang 2\/2/,'Late response cannot replace selected tab');
current.close();assert.equal(current.isConnected,false);
console.log('CHALLENGE_PAGINATION_OK: independent tabs, API pages, bounds, top20 unchanged, stale-response guard');
