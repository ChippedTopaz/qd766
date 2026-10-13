import assert from 'node:assert/strict';
import {renderPeerList,centerPeerLists} from '../dist/peer-list.js';
const items=[{id:'self',name:'Cơ quan mình',score:8},{id:'high',name:'Cơ quan cao',score:10},
 {id:'tie',name:'Đồng hạng',score:8},{id:'low',name:'Thấp',score:4},{id:'bad',name:'Thiếu điểm',score:NaN}];
const before=structuredClone(items);
const html=renderPeerList(items,'self');
assert.deepEqual(items,before,'Rendering never changes source data/order');
assert(html.indexOf('Cơ quan cao')<html.indexOf('Cơ quan mình'));
assert.match(html,/mine" aria-current="true"/);
assert.equal((html.match(/Hạng 2\/4/g)??[]).length,2);
assert.match(html,/Hạng 4\/4/);assert(!html.includes('Thiếu điểm'));
assert(!renderPeerList([{id:'self',name:'<unsafe>',score:0}],'self').includes('<unsafe>'));
function list({rowTop=700,rowHeight=40,height=200,scrollTop=0,missing=false}={}){
 return {clientHeight:height,clientTop:0,scrollHeight:1000,scrollTop,
  querySelector:()=>missing?null:{getBoundingClientRect:()=>({top:rowTop,height:rowHeight})},
  getBoundingClientRect:()=>({top:100})};
}
const middle=list(),first=list({rowTop:100}),last=list({rowTop:1090}),missing=list({missing:true,scrollTop:80}),hidden=list({height:0,scrollTop:15});
const root={querySelectorAll:selector=>{assert.equal(selector,'.comparison-card .nearby-list');return [middle,first,last,missing,hidden]}};
centerPeerLists(root);
assert.equal(middle.scrollTop,520);assert.equal(first.scrollTop,0);assert.equal(last.scrollTop,800);
assert.equal(missing.scrollTop,80);assert.equal(hidden.scrollTop,15);
console.log('PEER_LIST_PASS: cohort ranks/ties, immutable order, local centering, edge clamping and missing/hidden rows');
