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
    detailsCapturedAt:null,detailsAvailable:false,stale:true,message:"Đang sử dụng dữ liệu gần nhất."};
  data.snapshots[period.id+":all"]=snap;
}
const appRoot={innerHTML:"",setAttribute(){}};
const button=(nav)=>({dataset:{nav},handlers:{},addEventListener(kind,callback){this.handlers[kind]=callback;}});
const navs=[button("overview"),button("time"),button("peers"),button("quality"),button("formulas")];
const exportButton=button("");
const overviewTabs=["overview","details","analysis"].map(id=>({...button(""),dataset:{overviewTab:id}}));
const groupButtons=data.groupOrder.map(id=>({...button(""),dataset:{groupDetail:id}}));
const groupSteps=[-1,1].map(step=>({...button(""),dataset:{groupStep:String(step)}}));
const formulaButtons=data.groupOrder.map(id=>({...button(''),dataset:{formulaGroup:id}}));
const trendButtons=data.groupOrder.map(id=>({...button(""),dataset:{trendToggle:id},attrs:{},setAttribute(key,value){this.attrs[key]=value;}}));
const trendSeries=data.groupOrder.map(id=>({dataset:{trendSeries:id},attrs:{},setAttribute(key,value){this.attrs[key]=value;},removeAttribute(key){delete this.attrs[key];}}));
const formulaScrolls=[];
globalThis.document={
  title:"",
  querySelector(selector){return selector==="#app"?appRoot:selector==="[data-action=export]"?exportButton:selector.startsWith('#formula-')?{scrollIntoView(options){formulaScrolls.push({selector,options});}}:null;},
  querySelectorAll(selector){return selector==="[data-formula-group]"?formulaButtons:selector==="[data-overview-tab]"?overviewTabs:selector==="[data-group-detail]"?groupButtons:selector==="[data-group-step]"?groupSteps:selector==="[data-nav]"?navs:selector==="[data-trend-toggle]"?trendButtons:selector==="[data-trend-series]"?trendSeries:[];},
};
globalThis.window={setTimeout:(fn,delay)=>{const timer=setTimeout(fn,delay);timer.unref();return timer},clearTimeout};
globalThis.location={search:"",hash:"",pathname:"/"};
globalThis.history={state:null,replaceState(){}};
globalThis.scrollTo=()=>{};
const calls=[];
globalThis.fetch=async(url,options)=>{
  calls.push({url,method:options?.method??"GET"});
  let body;
  if(url==="/api/v1/access-policy")body={publicReadOnly:true,googleLoginEnabled:true};
  else if(url==="/api/v1/auth/me")body={name:'Admin test',role:'admin',accessTier:'nationwide',provinceId:rootId,csrfToken:'test',credits:100};
  else if(url==="/api/v1/me/trivia")body={available:false,question:null};
  else if(url==="/api/v1/dashboard?fast=true&compact=true")body=data;
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
const overviewStatus=appRoot.innerHTML.match(/<details class="bento-status">([\s\S]*?)<\/details>/)[1];
assert.equal(overviewStatus.match(/<summary>([\s\S]*?)<\/summary>/)[1],'<span class="status-toggle">ⓘ Thông tin dữ liệu</span>');
assert.doesNotMatch(overviewStatus,/status-chips|status-timestamps|Dữ liệu quá hạn|Hai thời điểm cập nhật|72 giờ|2 giờ/);
assert.doesNotMatch(appRoot.innerHTML,/<details class="bento-status" open/);
const periodOptions=appRoot.innerHTML.match(/<select id="period-value">([\s\S]*?)<\/select>/)[1];
assert(periodOptions.indexOf('value="month-2026-10"')<periodOptions.indexOf('value="month-2026-09"'));
assert.match(appRoot.innerHTML,/Chi tiết: Chưa xác định/);
assert.equal((appRoot.innerHTML.match(/data-trend-toggle=/g)||[]).length,6);
trendButtons[0].handlers.click();
assert.equal(trendButtons[0].attrs['aria-pressed'],'false');
assert.equal(trendSeries[0].attrs.hidden,'');
trendButtons[0].handlers.click();
assert.equal(trendButtons[0].attrs['aria-pressed'],'true');
assert(!('hidden' in trendSeries[0].attrs));
assert.doesNotMatch(appRoot.innerHTML,/Vấn đề cần ưu tiên|class="panel group-detail"/);
groupButtons[1].handlers.click();
assert.match(appRoot.innerHTML,/data-overview-tab="details" aria-selected="true"/);
assert.match(appRoot.innerHTML,/overview-group-nav/);
assert.match(appRoot.innerHTML,new RegExp(data.groupLabels[data.groupOrder[1]]));
assert.doesNotMatch(appRoot.innerHTML,/class="bento-top"|class="split bento-insights"/);
groupSteps[1].handlers.click();
assert.match(appRoot.innerHTML,new RegExp(data.groupLabels[data.groupOrder[2]]));
overviewTabs[2].handlers.click();
assert.match(appRoot.innerHTML,/Phân tích điểm số/);
assert.doesNotMatch(appRoot.innerHTML,/Kết quả tốt cần duy trì|analysis-group-result/);
assert.doesNotMatch(appRoot.innerHTML,/class="bento-top"|overview-group-nav/);
overviewTabs[0].handlers.click();
assert.match(appRoot.innerHTML,/class="bento-top"/);
assert.doesNotMatch(appRoot.innerHTML,/class="split bento-insights"|overview-group-nav/);
navs.find(n=>n.dataset.nav==="time").handlers.click();
assert.match(appRoot.innerHTML,/Chuỗi điểm cùng loại kỳ/);
assert.match(appRoot.innerHTML,/Tháng 9\/2026/);
assert.match(appRoot.innerHTML,/Tháng 10\/2026/);
assert.doesNotMatch(appRoot.innerHTML,/Hiện có một kỳ tháng/);
assert.match(appRoot.innerHTML,/<details class="comparison-notes"><summary>Lưu ý<\/summary>/);
assert.doesNotMatch(appRoot.innerHTML,/<details class="comparison-notes" open/);
navs.find(n=>n.dataset.nav==='peers').handlers.click();
assert.match(appRoot.innerHTML,/So sánh theo cơ quan/);
assert.match(appRoot.innerHTML,/Bảng xếp hạng/);
assert.doesNotMatch(appRoot.innerHTML,/Đơn vị liền kề trong xếp hạng|Quy mô hồ sơ tương đồng|Phân phối điểm/);
for(const group of data.groupOrder)assert.match(appRoot.innerHTML,new RegExp(data.groupLabels[group]));
assert.match(appRoot.innerHTML,/Không có cơ quan, đơn vị phù hợp/);
exportButton.handlers.click();
assert.match(appRoot.innerHTML,/data-export-excel="details" disabled/);
assert.match(appRoot.innerHTML,/data-export-excel="scores" >/);
navs.find(n=>n.dataset.nav==='quality').handlers.click();
const qualityNotes=appRoot.innerHTML.match(/<details class="comparison-notes">[\s\S]*?<\/details>/)?.[0];
assert(qualityNotes,'Quality notes must be opt-in');
assert.match(qualityNotes,/Chưa cập nhật được|Chỉ có điểm tổng hợp tỉnh/);
const qualityVisible=appRoot.innerHTML.replace(qualityNotes,'');
assert.doesNotMatch(qualityVisible,/Chưa cập nhật được|Số liệu tạm thời|Hai thời điểm cập nhật|Giới hạn hiện tại|Đang rà soát/);
assert.match(qualityVisible,/Thời điểm cập nhật theo nhóm chỉ tiêu/);
const qualityGrid=qualityVisible.match(/<section class="quality-grid">[\s\S]*?<\/section>/)?.[0]??'';
assert.equal((qualityGrid.match(/class="quality-card"/g)||[]).length,4);
for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
const callsBeforeFormulas=calls.length;
navs.find(n=>n.dataset.nav==="formulas").handlers.click();
assert.match(appRoot.innerHTML,/Công thức tính Bộ chỉ số 766/);
assert.equal((appRoot.innerHTML.match(/class="formula-card"/g)||[]).length,4);
formulaButtons.find(button=>button.dataset.formulaGroup==='provide-online-tree').handlers.click();
assert.deepEqual(formulaScrolls,[{selector:'#formula-provide-online-tree',options:{behavior:'smooth',block:'start'}}]);
assert.match(appRoot.innerHTML,/id="formula-provide-online-tree"/);
assert.doesNotMatch(appRoot.innerHTML,/id="formula-transparency"/);
assert.equal((appRoot.innerHTML.match(/class="formula-card"/g)||[]).length,3);
assert.equal(calls.length,callsBeforeFormulas);
assert(calls.every(call=>call.method==="GET"&&!call.url.includes("requests")&&!call.url.includes("jobs")));
console.log("SUMMARY_ONLY_UI_OK: actual renderer, history table, detail export disabled, GET-only");
