import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {comboTooltip,comboTickIndices,smoothSegments,renderComboGraphic,bindComboCharts,dailyComboOptions} from '../dist/daily-combo-chart.js';
const day=i=>{const d=new Date('2028-01-01T00:00:00Z');d.setUTCDate(d.getUTCDate()+i);return d.toISOString().slice(0,10)};
const points=Array.from({length:366},(_,i)=>({day:day(i),delta:i===0?null:i===60?-15:200,ratio:60+i/10,score:3,maximum:6}));
for(const count of [7,30,90,366])for(const width of [240,280,360,620,1200]){
 const model={name:'Chỉ tiêu',mode:'ratio',points:points.slice(0,count)},plot=width-dailyComboOptions.left-dailyComboOptions.right;
 const indices=comboTickIndices(count,plot);
 for(let i=1;i<indices.length;i++)assert((indices[i]-indices[i-1])*plot/count>=dailyComboOptions.tickSpacing,'Tick labels never overlap');
 const svg=renderComboGraphic(model,width);
 assert.equal([...svg.matchAll(/data-daily-combo-date=/g)].length,count,'All dates kept, only labels skipped');
 assert.equal([...svg.matchAll(/data-combo-tick=/g)].length,indices.length);
 assert.doesNotMatch(svg,/NaN|Infinity/);assert.match(svg,/Tỷ lệ \(%\)/);assert.match(svg,/stroke="#ea8809"/);
}
const model={name:'Example',mode:'ratio',points:points.slice(0,90)};
// Both sides share five exact Y coordinates; Y1 has only integers, zero below.
for(const delta of [0,1,2,7,21,1001,-15]){
 const svg=renderComboGraphic({name:'Integer axis',mode:'ratio',points:[{...points[1],delta}]},360);
 const left=[...svg.matchAll(/data-combo-y1="([^"]+)"[^>]* y="([^"]+)"/g)];
 const right=[...svg.matchAll(/data-combo-y2="([^"]+)"[^>]* y="([^"]+)"/g)];
 assert.equal(left.length,dailyComboOptions.tickIntervals+1);assert.equal(right.length,left.length);
 assert(left.every(t=>Number.isInteger(Number(t[1]))&&Number(t[1])>=0));
 assert.deepEqual(left.map(t=>t[2]),right.map(t=>t[2]),'Both axes align exactly with shared horizontal lines');
 assert.equal(Number(left.at(-1)[1]),0);assert.match(svg,/y1="248" y2="248" class="daily-combo-zero"/);
 if(delta>=0){assert.match(svg,/fill="#3b82f6" fill-opacity="0.4"/);assert.doesNotMatch(svg,/data-combo-correction/);}
 else {assert.match(svg,/data-combo-correction/);assert.doesNotMatch(svg,/<rect/,'Negative correction never creates a bar below zero');}
}
const css=readFileSync(new URL('../bento.css',import.meta.url),'utf8');
assert.match(css,/\.daily-combo-bar-key\{background:#3b82f6;opacity:\.4\}/);
assert.match(css,/\.daily-indicator-panel \.daily-indicator-table th:not\(:first-child\),\.daily-indicator-panel \.daily-indicator-table td:not\(:first-child\)\{text-align:right;font-variant-numeric:tabular-nums\}/);
const preview=readFileSync(new URL('../daily-combo-preview.html',import.meta.url),'utf8');
assert.deepEqual([...preview.matchAll(/data-range="(\d+)"/g)].map(m=>Number(m[1])),[7,30,90],'Only approved preview ranges');
assert.doesNotMatch(preview,/366 ngày|size===366/);
assert.match(preview,/const delta=Math\.round\(30\+\(i\*47%180\)\)/);assert.doesNotMatch(preview,/i===3\?-20/);
assert.equal(comboTooltip(model,1),'Ngày: 02/01/2028\nPhát sinh: +200\nTỷ lệ: 60,1%');
assert.match(comboTooltip(model,0),/Phát sinh: —/);assert.match(comboTooltip(model,60),/Phát sinh: -15/);
assert.match(comboTooltip({...model,mode:'score'},1),/Điểm số: 3 điểm/);
assert.match(comboTooltip({name:'Missing',mode:'ratio',points:[{day:day(0),delta:0,ratio:null,score:null,maximum:null}]},0),/Phát sinh: 0\nTỷ lệ: —/);
const paths=smoothSegments([{x:0,y:0},{x:10,y:10},null,{x:30,y:20},{x:40,y:10}]);
assert.equal(paths.length,2,'Line must split at missing observations');
const monotone=smoothSegments([{x:0,y:0},{x:10,y:100},{x:20,y:101}])[0];
const coordinates=[...monotone.matchAll(/C ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)/g)];
assert(coordinates.every((c,i)=>[Number(c[2]),Number(c[4])].every(y=>y>=(i?100:0)&&y<=(i?101:100))),'Smooth controls preserve bounds');
// DOM adapter test: hover/touch and keyboard share the same exact tooltip.
let width=360,observer,disconnected=0;const events={},hover={attributes:{hidden:''},setAttribute(k,v){this.attributes[k]=v},removeAttribute(k){delete this.attributes[k]}};
const tip={hidden:true,textContent:'',style:{},offsetWidth:170};
const graphic={dataset:{},innerHTML:'',querySelector(){return hover},getBoundingClientRect(){return {left:0,width}}};
const host={dataset:{dailyCombo:JSON.stringify(model)},get clientWidth(){return width},querySelector(s){return s==='[data-combo-graphic]'?graphic:tip},addEventListener(k,f){events[k]=f}};
const previousObserver=globalThis.ResizeObserver;
try{
 globalThis.ResizeObserver=class{constructor(fn){observer=fn}observe(){}disconnect(){disconnected++}};
 const dispose=bindComboCharts({querySelectorAll(){return [host]}});
 events.keydown({key:'End',preventDefault(){}});assert.equal(tip.textContent,comboTooltip(model,89));assert.equal(tip.hidden,false);
 events.keydown({key:'Home',preventDefault(){}});assert.equal(tip.textContent,comboTooltip(model,0));
 events.pointerdown({clientX:width-dailyComboOptions.right-1});assert.equal(tip.textContent,comboTooltip(model,89));
 events.pointermove({clientX:0});assert.equal(tip.hidden,true);
 width=280;observer();assert.match(graphic.innerHTML,/viewBox="0 0 280 290"/);
 events.keydown({key:'Escape',preventDefault(){}});assert.equal(tip.hidden,true);
 dispose();assert.equal(disconnected,1,'Observer removed when panel changes');
}finally{globalThis.ResizeObserver=previousObserver;}
console.log('DAILY_COMBO_CHART_PASS: dual axes, 7/30/90/366 dates, responsive tick spacing, smooth gap-safe paths, signed deltas, hover/touch/keyboard and observer cleanup');
