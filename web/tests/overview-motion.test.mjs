import assert from 'node:assert/strict';
import {transitionOverview,cancelOverviewMotion} from '../dist/overview-motion.js';
let layout='overview',reduced=false,created=[],animations=[],cards=[];
const rect=(x,y,w,h)=>({left:x,top:y,width:w,height:h,right:x+w,bottom:y+h});
function node(key,r){
 const title={textContent:key,getBoundingClientRect:()=>rect(r.left+12,r.top+12,r.width-24,36)};
 return {dataset:{motionCard:key},style:{removeProperty(name){delete this[name]}},
  classList:{add(){},remove(){}},querySelector:()=>title,getBoundingClientRect:()=>r,
  animate(frames,options){const a={frames,options,cancelled:false,cancel(){this.cancelled=true}};animations.push(a);return a;}};
}
function surface(){
 const el=node('',rect(100,100,100,100));
 el.setAttribute=()=>{};el.remove=()=>{el.removed=true};
 created.push(el);return el;
}
globalThis.getComputedStyle=()=>({background:'#fff',border:'1px solid #eee',borderRadius:'16px',boxShadow:'none',color:'#333',font:'12px sans-serif',lineHeight:'18px',textAlign:'left'});
globalThis.window={innerWidth:1600,matchMedia:()=>({matches:reduced}),addEventListener(){},removeEventListener(){}};
globalThis.document={body:{append(){}},createElement:surface,
 querySelector:s=>s==='[data-overview-layout]'?{dataset:{overviewLayout:layout}}:null,
 querySelectorAll:s=>s.includes('[data-motion-card]')?cards:[]};
function set(mode){layout=mode;cards=Array.from({length:7},(_,i)=>node(String(i),mode==='overview'?rect(300+i*90,250+i*45,250,160):rect(300+i*145,180,135,110)));}
set('overview');transitionOverview(()=>set('details'));
assert.equal(created.length,14);assert.equal(animations.filter(a=>a.options.duration===900&&a.options.easing==='cubic-bezier(.4,0,.2,1)').length,7);
assert.equal(animations.filter(a=>a.options.duration===380&&a.options.delay===450).length,7);
assert(cards.every(c=>c.style.opacity==='0'));
transitionOverview(()=>set('overview')); // Reversing mid-flight cancels prior surfaces safely.
assert(created.slice(0,14).every(s=>s.removed));assert(animations.slice(0,21).every(a=>a.cancelled));
cancelOverviewMotion();assert(created.every(s=>s.removed));assert(cards.every(c=>c.style.opacity===undefined));
const count=created.length;
reduced=true;transitionOverview(()=>set('details'));assert.equal(created.length,count);
assert.equal(layout,'details');
reduced=false;transitionOverview(()=>set('details'));assert.equal(created.length,count);
set('overview');cards.forEach(c=>delete c.animate);transitionOverview(()=>{layout='details'});assert.equal(created.length,count);
cancelOverviewMotion();
console.log('OVERVIEW_MOTION_PASS: seven transitions, interruption cleanup, reduced-motion and no-animation fallback');
