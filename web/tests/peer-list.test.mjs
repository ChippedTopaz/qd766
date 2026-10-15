import assert from 'node:assert/strict';
import {renderPeerList,centerPeerLists,peerRankChange,peerComparisonContext} from '../dist/peer-list.js';
const items=[{id:'self',name:'Cơ quan mình',score:8},{id:'high',name:'Cơ quan cao',score:10},
 {id:'tie',name:'Đồng hạng',score:8},{id:'low',name:'Thấp',score:4},{id:'bad',name:'Thiếu điểm',score:NaN}];
const before=structuredClone(items);
const html=renderPeerList(items,'self');
assert.deepEqual(items,before,'Rendering never changes source data/order');
assert(html.indexOf('Cơ quan cao')<html.indexOf('Cơ quan mình'));
assert.match(html,/mine" aria-current="true"/);
assert.doesNotMatch(html,/Hạng/);assert.match(html,/STT/);assert(!html.includes('Thiếu điểm'));
assert.equal((html.match(/class="peer-index"/g)||[]).length,4);
assert.deepEqual(peerRankChange(items,'self'),{rank:2,total:4,change:null});
assert.match(peerComparisonContext(items,'self','Xã, phường · Phú Thọ'),/Hạng <b>2\/4/);
const old=[{id:'high',name:'Cao',score:10},{id:'self',name:'Mình',score:1},{id:'tie',name:'Đồng hạng',score:8},{id:'low',name:'Thấp',score:4}];
const baseline={rows:old,label:'So với tháng trước'};
assert.equal(peerRankChange(items,'self',baseline).change,2);
assert.match(peerComparisonContext(items,'self','Xã, phường',baseline),/↑ 2 bậc/);
assert.equal(peerRankChange(old,'self',{rows:items,label:'So với trước'}).change,-2);
assert.equal(peerRankChange(items,'self',{rows:items,label:'So với trước'}).change,0);
assert.match(peerComparisonContext(items,'self','Xã, phường',{rows:items,label:'Mốc'}),/Không đổi/);
assert.equal(peerRankChange(items,'self',{rows:old.slice(0,3),label:'Mốc'}).change,null,'Changed cohort cannot imply improvement');
assert.equal(peerRankChange(items,'self',{rows:old,currentRows:old,label:'Mốc'}).change,null,'Latest scores must match the saved daily observation');
assert.equal(peerRankChange(items,'missing',baseline).rank,null);
assert.doesNotMatch(peerComparisonContext(items,'self','<script>',{rows:old,label:'<img>'}),/<script>|<img>/);
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
