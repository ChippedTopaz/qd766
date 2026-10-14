import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
for(const scope of ['all','formality']){
 const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
 const snap=Object.values(data.snapshots).find(s=>s.scope==='all');
 const agency=data.units.find(u=>u.departmentLevel==='PROVINCE');
 const group=snap.datasets.find(d=>d.group==='formality-online-payment-tree');
 const own=group.children.find(e=>e.departmentId===agency.departmentId);
 const peer=group.children.find(e=>e.departmentId!==agency.departmentId&&e.departmentLevel===own.departmentLevel);
 assert(own&&peer);data.defaultUnitId=agency.departmentId;
 const parameters={totalFeeDossierFormality:8,totalFeeFormality:40,totalDossierOnlineFormalityPaymentSuccess:18,totalFeeDossierFormalityDistinct:40,totalDossierOnlinePaymentSuccess:80,totalDossierFinancialObligation:100,
 agencyPaymentProvidedNumerator:8,agencyPaymentProvidedDenominator:40,agencyPaymentTransactionsNumerator:18,agencyPaymentTransactionsDenominator:40};
 own.parameters=parameters;own.metrics=[];
 const scores=[.8,1.5,6],keys=['payment:3.5','payment:3.5b','payment:3.6'];
 peer.parameters={};peer.metrics=[];peer.comparisonPoints=Object.fromEntries(keys.map((key,i)=>[key,{score:scores[i],maximum:[2,2,6][i]}]));
 snap.scope=scope;snap.formalityId=scope==='formality'?data.formality.id:null;
 data.periods=[{id:'month-2026-09',label:'Tháng 9/2026',type:'month',year:2026,value:9,provisional:false}];
 data.snapshots={'month-2026-09:all':{...structuredClone(snap),scope:'all',formalityId:null},['month-2026-09:'+scope]:snap};
 const app={innerHTML:'',setAttribute(){},querySelector(){return null},querySelectorAll(){return []}},control=dataset=>({dataset,handlers:{},addEventListener(kind,cb){this.handlers[kind]=cb}});
 let peerControls=[],metrics=[];const nav=control({nav:'peers'});
 globalThis.document={title:'',querySelector:s=>s==='#app'?app:null,querySelectorAll(s){
  if(s==='[data-nav]')return [nav];
  if(s==='[data-peer-unit]'){peerControls=[...app.innerHTML.matchAll(/data-peer-unit="([^"]+)"(?: data-peer-group="([^"]+)")?/g)].map(m=>control({peerUnit:m[1],peerGroup:m[2]}));return peerControls}
  if(s==='[data-metric-detail]'){metrics=[...app.innerHTML.matchAll(/data-metric-detail="([^"]+)"/g)].map(m=>control({metricDetail:m[1]}));return metrics}
  return [];
 }};
 globalThis.window={setTimeout:(fn,delay)=>{const timer=setTimeout(fn,delay);timer.unref();return timer},clearTimeout};
 globalThis.location={search:'?period=month-2026-09&scope='+scope+'&unit='+agency.departmentId+'&formality='+data.formality.id,hash:'',pathname:'/'};
 globalThis.history={state:null,replaceState(){}};globalThis.scrollTo=()=>{};
 const calls=[];globalThis.fetch=async(url,options)=>{calls.push(options?.method??'GET');const body=url==='/api/v1/access-policy'?{publicReadOnly:true,googleLoginEnabled:true,paidRequestsEnabled:true}:
 url==='/api/v1/auth/me'?{id:'account',name:'Test account',role:'admin',accessTier:'national',provinceId:data.province.id,trialAdmitted:true,canCollect:true,csrfToken:'test'}:
 url==='/api/v1/dashboard?fast=true&compact=true'?data:
 url.startsWith('/api/v1/me/formalities?')?{items:[data.formality]}:
 url.startsWith('/api/v1/me/formality-requests?')?{items:[],availableCredits:10,reservedCredits:0}:
 url.startsWith('/api/v1/dashboard/selection?')?{snapshot:snap,metadata:{detailsAvailable:true}}:[];
 return {ok:true,status:200,json:async()=>structuredClone(body)}};
 await import('../dist/app.js?payment-ui='+scope);for(let i=0;i<6;i++)await new Promise(r=>setImmediate(r));
 assert.equal(typeof nav.handlers.click,'function',scope+': '+app.innerHTML.slice(0,500));nav.handlers.click();
 const entry=peerControls.find(c=>c.dataset.peerUnit===agency.departmentId&&c.dataset.peerGroup===group.group);assert(entry);entry.handlers.click();
 const initialComparison=app.innerHTML.match(/<aside class="comparison-card"><h3>So với đơn vị cùng cấp<\/h3>([\s\S]*?)<\/aside>/)?.[1];
 assert(initialComparison,'Group-level peer panel opens before selecting any metric');
 assert.match(initialComparison,/Thứ hạng trong tỉnh/,'Initial group panel shows provincial same-level rank');
 assert.match(initialComparison,/aria-current="true"/,'Selected agency is marked for local centering');
 for(const key of keys){
  const row=metrics.find(m=>m.dataset.metricDetail===key);assert(row,'Scored payment row is bound');
  assert.match(app.innerHTML,new RegExp('<tr[^>]*data-metric-detail="'+key.replace('.','\\.')+'"'),'Click handler belongs to the row, not only the name');
  const before=app.innerHTML;
  row.handlers.click({target:{closest(){return {matches(){return false}}}}});
  assert.equal(app.innerHTML,before,'An independent control in the row keeps its own action');
  row.handlers.click({target:{closest(){return null}}});
  assert.match(app.innerHTML,/metric-comparison/,'Click switches right-side comparison to component score');
  assert.match(app.innerHTML,/So sánh chỉ tiêu với đơn vị cùng cấp/);
  assert.match(app.innerHTML,new RegExp('class="selectable-row selected" data-metric-detail="'+key.replace('.','\\.')+'"'));
  assert(app.innerHTML.includes(peer.departmentName));
 }
 assert(calls.every(m=>m==='GET'),'Selection does not collect or charge credits');
}
console.log('PAYMENT_COMPARISON_UI_PASS: actual app click handlers switch right-hand peer comparison for all three scores in all/formality scopes');
