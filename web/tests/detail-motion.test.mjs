import assert from 'node:assert/strict';
import {transitionDetail,cancelOverviewMotion} from '../dist/overview-motion.js';
let selected='total',mobile=false,reduced=false,animations=[],copies=[];
const keys=['total','a','b'];
function body(){return {style:{},attributes:[{name:'id'},{name:'data-overview-content'}],classList:{remove(){}},
 removeAttribute(name){this.attributes=this.attributes.filter(a=>a.name!==name)},setAttribute(name,value){this[name]=value},querySelectorAll(){return []},
 remove(){this.removed=true},cloneNode(){const copy=body();copies.push(copy);return copy},
 getBoundingClientRect(){return {left:260,top:350,width:900,height:700}},
 animate(frames,options){const a={frames,options,cancel(){this.cancelled=true}};animations.push(a);return a}}}
let content=body();
globalThis.window={innerHeight:900,matchMedia:q=>({matches:q.includes('reduce')?reduced:mobile}),addEventListener(){},removeEventListener(){}};
globalThis.document={body:{append(){}},querySelector:s=>s==='.overview-score-strip'?{
 querySelectorAll:()=>keys.map(k=>({dataset:{motionCard:k}})),querySelector:()=>({dataset:{motionCard:selected}})}:s==='[data-overview-content]'?content:null,querySelectorAll:()=>[]};
const update=key=>()=>{cancelOverviewMotion();selected=key;content=body()};
transitionDetail(update('b'),'b');
assert.equal(animations.length,2);assert.equal(animations[1].frames[0].transform,'translateX(48px)');
assert.equal(copies[0]['aria-hidden'],'true');assert.equal(copies[0].inert,'');assert.equal(copies[0].attributes.length,0);
transitionDetail(update('a'),'a');assert(copies[0].removed);assert(animations[0].cancelled);
assert.equal(animations.at(-1).frames[0].transform,'translateX(-48px)');
cancelOverviewMotion();assert(copies.every(c=>c.removed));
mobile=true;const count=copies.length;transitionDetail(update('total'),'total');
assert.equal(copies.length,count);assert.equal(animations.at(-1).frames[0].transform,'translateX(0px)');
cancelOverviewMotion();reduced=true;const before=animations.length;
transitionDetail(update('b'),'b');assert.equal(animations.length,before);assert.equal(selected,'b');
reduced=false;transitionDetail(update('b'),'b');assert.equal(animations.length,before);
cancelOverviewMotion();console.log('DETAIL_MOTION_PASS: direction, inert outgoing copy, interruption, mobile fade, reduced-motion and same-selection');
