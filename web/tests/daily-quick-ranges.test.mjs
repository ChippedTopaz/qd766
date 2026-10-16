import assert from 'node:assert/strict';
import {dailyQuickRanges,renderIndicatorComparison,DailyIndicatorPanel} from '../dist/daily-indicator-comparison.js';
const dates=(end,count)=>Array.from({length:count},(_,i)=>{const d=new Date(end+'T00:00:00Z');d.setUTCDate(d.getUTCDate()-i);return d.toISOString().slice(0,10);});
const entity={departmentId:'unit',departmentName:'Unit',apiScore:1,apiMaxScore:10,metrics:[],parameters:{}};
const day=date=>({reportDate:date,capturedAt:null,entity,state:'available'});
const fixture=(end,count)=>({scope:'all',group:'formality-online-payment-tree',unitId:'unit',unitName:'Unit',availableDates:dates(end,count),current:day(end),baseline:day(dates(end,2)[1]),series:[]});
for(const [count,expected] of [[6,[]],[7,[7]],[29,[7]],[30,[7,30]],[89,[7,30]],[90,[7,30,90]]]){
 const body=fixture('2026-12-31',count),original=JSON.stringify(body);
 assert.deepEqual(dailyQuickRanges(body).map(r=>r.days),expected);
 assert.equal(JSON.stringify(body),original,'Does not mutate data or selection');
 const html=renderIndicatorComparison(body);
 assert.deepEqual([...html.matchAll(/data-daily-indicator-range="(\d+)"/g)].map(m=>Number(m[1])),expected);
 assert.match(html,/data-daily-indicator-date="baseline"/);assert.match(html,/data-daily-indicator-date="current"/);
}
const body=fixture('2026-12-31',90);
assert.deepEqual(dailyQuickRanges(body),[{days:7,baseline:'2026-12-25'},{days:30,baseline:'2026-12-02'},{days:90,baseline:'2026-10-03'}]);
const gap=structuredClone(body);gap.availableDates=gap.availableDates.filter(d=>d!=='2026-12-20');
assert.deepEqual(dailyQuickRanges(gap).map(r=>r.days),[7],'No 30/90-day shortcut across a missing day');
const missingCurrent=structuredClone(body);missingCurrent.current.state='missing';assert.deepEqual(dailyQuickRanges(missingCurrent),[]);
const historical=structuredClone(body);historical.current=day('2026-12-10');
assert.equal(dailyQuickRanges(historical)[0].baseline,'2026-12-04','Anchor to selected day, not wall-clock/latest');
assert.deepEqual(dailyQuickRanges(fixture('2026-10-06',6)),[],'Period-scoped dates do not borrow prior-period observations');
assert.equal(dailyQuickRanges(fixture('2028-03-01',7))[0].baseline,'2028-02-24','UTC leap-year calendar');
body.baseline=day('2026-12-25');
assert.match(renderIndicatorComparison(body),/data-daily-indicator-range="7" aria-pressed="true"/);

// Real panel handler: exactly one GET, same context/end date, selected indicator
// retained; repeat/double click guarded, no collection or Credit mutation.
let calls=[],changed=0,buttons=[];
const context={accountId:'account',provinceId:'province',unitId:'unit',unitName:'Unit',group:body.group,period:{id:'year-2026',type:'year',year:2026,value:null}};
const read=async(url,options)=>{calls.push({url,options});const q=new URL(url,'https://test.local').searchParams;
 return {ok:true,json:async()=>({...body,current:day(q.get('current_date')??'2026-12-31'),baseline:day(q.get('baseline_date')??'2026-12-30')})};};
const panel=new DailyIndicatorPanel(()=>changed++,read);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
panel.render(context);await settle();
const doc={querySelector(){return null;},querySelectorAll(selector){
 if(selector==='[data-daily-indicator-range]')return buttons;
 return [];
}};
const button=days=>({dataset:{dailyIndicatorRange:String(days)},addEventListener(_event,fn){this.click=fn;}});
buttons=[button(7),button(30),button(90),button(366)];panel.bind(context,doc);
const initial=calls.length;buttons[1].click();buttons[1].click();await settle();
assert.equal(calls.length,initial+1);
const q=new URL(calls.at(-1).url,'https://test.local').searchParams;
assert.equal(q.get('baseline_date'),'2026-12-02');assert.equal(q.get('current_date'),'2026-12-31');
assert.equal(q.get('scope'),'all');assert.equal(q.get('unit_id'),'unit');assert.equal(q.get('period_type'),'year');
assert.match(panel.render(context),/data-daily-indicator-range="30" aria-pressed="true"/);
buttons[1].click();buttons[3].click();await settle();assert.equal(calls.length,initial+1);
panel.pause();buttons[0].click();await settle();assert.equal(calls.length,initial+1,'Stale control cannot read another active context');
assert(calls.every(c=>!c.options.method||c.options.method==='GET'));assert(changed>0);
console.log('DAILY_QUICK_RANGES_PASS: 7/30/90 complete inclusive windows, gaps, period/date anchor, leap year, active button, one GET, double-click/stale guards');
