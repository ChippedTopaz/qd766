// Render smoke test, not visual/browser acceptance. No source/network calls.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const data=JSON.parse(readFileSync(new URL("../data/snapshots.json",import.meta.url)));
const original=Object.values(data.snapshots).find(s=>s.scope==="all");
const rootId=data.province.id;
data.defaultUnitId=rootId;
data.periods=[{id:"month-2026-09",label:"Tháng 9/2026",type:"month",year:2026,value:9,provisional:false},
  {id:"month-2026-10",label:"Tháng 10/2026",type:"month",year:2026,value:10,provisional:true}];
data.snapshots={};
for(const period of data.periods){
  const snap=structuredClone(original);
  snap.datasets=snap.datasets.map(dataset=>({...dataset,children:[],
    root:{...dataset.root,metrics:[],parameters:{}}}));
  snap.delivery={result:"national-summary",capturedAt:"2026-10-02T16:00:00Z",
    detailsCapturedAt:null,detailsAvailable:false,stale:false};
  data.snapshots[period.id+":all"]=snap;
}
const appRoot={innerHTML:""};
const button=(nav)=>({dataset:{nav},handlers:{},addEventListener(kind,callback){this.handlers[kind]=callback;}});
const navs=[button("overview"),button("time"),button("quality"),button("formulas")];
const exportButton=button("");
const trendButtons=data.groupOrder.map(id=>({...button(""),dataset:{trendToggle:id},attrs:{},setAttribute(key,value){this.attrs[key]=value;}}));
const trendSeries=data.groupOrder.map(id=>({dataset:{trendSeries:id},attrs:{},setAttribute(key,value){this.attrs[key]=value;},removeAttribute(key){delete this.attrs[key];}}));
globalThis.document={
  title:"",
  querySelector(selector){return selector==="#app"?appRoot:selector==="[data-action=export]"?exportButton:null;},
  querySelectorAll(selector){return selector==="[data-nav]"?navs:selector==="[data-trend-toggle]"?trendButtons:selector==="[data-trend-series]"?trendSeries:[];},
};
globalThis.window={setTimeout};
globalThis.scrollTo=()=>{};
const calls=[];
globalThis.fetch=async(url,options)=>{
  calls.push({url,method:options?.method??"GET"});
  let body;
  if(url==="/api/v1/access-policy")body={publicReadOnly:true};
  else if(url==="/api/v1/dashboard")body=data;
  else if(url==="/api/v1/dashboard/provinces")body=[];
  else if(url.startsWith("/api/v1/dashboard/province-rankings"))body=Array.from({length:34},(_,i)=>({
    rootDepartmentId:i===0?rootId:"province-"+i,provinceName:"Tỉnh "+i,
    totalScore:60+i/10,totalMaximum:100,capturedAt:"2026-10-02T16:00:00Z",
    groups:Object.fromEntries(data.groupOrder.map(group=>[group,{score:5,maximum:10,parameters:{},metrics:{}}]))
  }));
  else throw new Error("Unexpected request "+url);
  return {ok:true,status:200,json:async()=>structuredClone(body)};
};
await import("../dist/app.js");
for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
assert.match(appRoot.innerHTML,/Chỉ có điểm tổng hợp tỉnh/);
assert.match(appRoot.innerHTML,/Chi tiết: Chưa xác định/);
assert.equal((appRoot.innerHTML.match(/data-trend-toggle=/g)||[]).length,6);
trendButtons[0].handlers.click();
assert.equal(trendButtons[0].attrs['aria-pressed'],'false');
assert.equal(trendSeries[0].attrs.hidden,'');
trendButtons[0].handlers.click();
assert.equal(trendButtons[0].attrs['aria-pressed'],'true');
assert(!('hidden' in trendSeries[0].attrs));
navs.find(n=>n.dataset.nav==="time").handlers.click();
assert.match(appRoot.innerHTML,/Chuỗi điểm cùng loại kỳ/);
assert.match(appRoot.innerHTML,/Tháng 9\/2026/);
assert.match(appRoot.innerHTML,/Tháng 10\/2026/);
assert.doesNotMatch(appRoot.innerHTML,/Hiện có một kỳ tháng/);
exportButton.handlers.click();
assert.match(appRoot.innerHTML,/data-export-excel="details" disabled/);
assert.match(appRoot.innerHTML,/data-export-excel="scores" >/);
const callsBeforeFormulas=calls.length;
navs.find(n=>n.dataset.nav==="formulas").handlers.click();
assert.match(appRoot.innerHTML,/Công thức tính Bộ chỉ số 766/);
assert.equal((appRoot.innerHTML.match(/class="formula-card"/g)||[]).length,21);
assert.equal(calls.length,callsBeforeFormulas);
assert(calls.every(call=>call.method==="GET"&&!call.url.includes("requests")&&!call.url.includes("jobs")));
console.log("SUMMARY_ONLY_UI_OK: actual renderer, history table, detail export disabled, GET-only");
