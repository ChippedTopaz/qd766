import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const template=Object.values(data.snapshots).find(s=>s.scope==='all');
data.periods=[];data.snapshots={};
for(const type of ['month','quarter','year'])for(const index of [1,2]){
 const id=type+'-'+index,p={id,label:type+' '+index,type,year:type==='year'?2024+index:2026,value:type==='year'?null:index,provisional:false};
 data.periods.push(p);const s=structuredClone(template);s.provinceAggregatedScore=60+index;
 for(const group of s.datasets){group.root.apiScore=10+index;group.root.apiMaxScore=20;}
 data.snapshots[id+':all']=s;
}
data.periods.push({id:'year-missing',label:'Năm chưa có dữ liệu',type:'year',year:2027,value:null,provisional:true});
const app={innerHTML:'',setAttribute(){}};let tabs=[],kind,periodControls=[];
const control=dataset=>({dataset,handlers:{},addEventListener(k,cb){this.handlers[k]=cb}});
const nav=control({nav:'time'});
globalThis.document={title:'',querySelector:s=>s==='#app'?app:null,querySelectorAll(s){
 if(s==='[data-nav]')return [nav];
 if(s==='[data-time-tab]'){tabs=['default','custom'].map(timeTab=>control({timeTab}));return tabs;}
 if(s==='[data-time-kind]'){kind=control({});return [kind];}
 if(s==='[data-time-period]'){periodControls=['baseline','current'].map(timePeriod=>control({timePeriod}));return periodControls;}
 return [];
}};
globalThis.window={setTimeout:(fn,delay)=>{const timer=setTimeout(fn,delay);timer.unref();return timer},clearTimeout};
globalThis.location={search:'?period=month-2',hash:'',pathname:'/'};
globalThis.history={state:null,replaceState(){}};globalThis.scrollTo=()=>{};
const calls=[];
globalThis.fetch=async(url,options)=>{calls.push({url,options});return {ok:!url.includes('/selection'),status:url.includes('/selection')?404:200,json:async()=>structuredClone(url==='/api/v1/access-policy'?{publicReadOnly:true}:url==='/api/v1/dashboard?fast=true&compact=true'?data:[])}};
await import('../dist/app.js?custom-ui');for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r));
nav.handlers.click();const original=app.innerHTML.match(/<tbody>[\s\S]*?<\/tbody>/)[0];
tabs[1].handlers.click();
for(const type of ['month','quarter','year']){
 kind.value=type;kind.handlers.change();
 periodControls[0].value=type+'-1';periodControls[0].handlers.change();
 periodControls[1].value=type+'-2';periodControls[1].handlers.change();
 const body=app.innerHTML.match(/<tbody>[\s\S]*?<\/tbody>/)[0];
 assert.equal((body.match(/<tr>/g)??[]).length,2);assert.match(body,/\+1,00/);
 assert.match(body,new RegExp(type+' 1'));assert.match(body,new RegExp(type+' 2'));
 const baselineOptions=app.innerHTML.match(/<select data-time-period="baseline"[^>]*>([\s\S]*?)<\/select>/)[1];
 const currentOptions=app.innerHTML.match(/<select data-time-period="current"[^>]*>([\s\S]*?)<\/select>/)[1];
 assert.doesNotMatch(baselineOptions,new RegExp('value="'+type+'-2"'));
 assert.doesNotMatch(currentOptions,new RegExp('value="'+type+'-1"'));
 const before=body;
 periodControls[0].value=type+'-2';periodControls[0].handlers.change();
 assert.equal(app.innerHTML.match(/<tbody>[\s\S]*?<\/tbody>/)[0],before,'Duplicate selection is rejected even when forged');
}
periodControls[1].value='year-missing';periodControls[1].handlers.change();
for(let i=0;i<8;i++)await new Promise(r=>setImmediate(r));
assert.match(app.innerHTML,/Kỳ được chọn chưa có dữ liệu/);
assert.equal(calls.filter(c=>c.url.includes('/selection')).length,1);
assert.ok(calls.every(c=>!c.options?.method||c.options.method==='GET'),'No acquisition or Credit mutation');
tabs[0].handlers.click();assert.equal(app.innerHTML.match(/<tbody>[\s\S]*?<\/tbody>/)[0],original,'Default table and globally selected month unchanged');
assert.equal(calls.filter(c=>c.url.includes('daily-history')).length,0,'Default and period custom tabs do not fetch daily history');
console.log('TIME_CUSTOM_UI_OK: month/quarter/year pair selection, 404, GET-only, default unchanged');
