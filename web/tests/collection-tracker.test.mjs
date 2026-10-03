import assert from 'node:assert/strict';
import {CollectionTracker} from '../dist/collection-tracker.js';
const timers=[],events=[],reads=[];
const responses=[new Error('temporary status failure'),{state:'running'},{state:'succeeded'}];
const tracker=new CollectionTracker((r,complete)=>events.push({...r,complete}),async url=>{
  reads.push(url);const result=responses.shift();if(result instanceof Error)throw result;return result;
},(callback,delay)=>timers.push({callback,delay}));
const request={id:'shared',kind:'job',key:'province-A:month-9:formality-X',label:'Tỉnh A · Tháng 9/2026 · X',state:'blocked',message:'Chờ kết nối nguồn'};
tracker.track({...request});tracker.track({...request});
assert.equal(timers.length,1,'Same job has one polling loop');
assert(tracker.hasActive(request.key));
async function tick(){timers.shift().callback();await new Promise(resolve=>setImmediate(resolve));}
await tick();assert.equal(events.at(-1).state,'unavailable');assert.equal(timers[0].delay,20000);
assert.equal(events.at(-1).complete,false);
await tick();assert.equal(events.at(-1).state,'running');
await tick();assert.equal(events.at(-1).complete,true);assert.equal(events.at(-1).key,request.key);
assert.equal(timers.length,0);assert.equal(tracker.hasActive(request.key),false);
assert(reads.every(url=>url==='/api/v1/collection-jobs/shared'));
for(const state of ['failed','halted','cancelled','canceled']){
  const callbacks=[],results=[];
  const terminal=new CollectionTracker((r,done)=>results.push({state:r.state,done}),async()=>({state}),cb=>callbacks.push(cb));
  terminal.track({...request,id:state});callbacks.shift()();await new Promise(resolve=>setImmediate(resolve));
  assert.equal(results.at(-1).state,state);assert.equal(results.at(-1).done,false);assert.equal(callbacks.length,0);
}
const callbacks=[],results=[];
const batch=new CollectionTracker((r,done)=>results.push({...r,done}),async()=>({state:'succeeded',totalItems:4,availableItems:1,completedItems:3}),cb=>callbacks.push(cb));
batch.track({...request,id:'batch',kind:'batch'});callbacks.shift()();await new Promise(resolve=>setImmediate(resolve));
assert.equal(results.at(-1).message,'Đã hoàn thành 4/4 TTHC.');assert(results.at(-1).done);
console.log('COLLECTION_TRACKER_OK: dedup, blocked tracking, transient retry, contextual completion, terminal states, batch progress');
