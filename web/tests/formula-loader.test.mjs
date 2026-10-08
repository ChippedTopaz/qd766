import {test} from 'node:test';
import assert from 'node:assert/strict';
import {defaultFormulaConfiguration,renderFormulaReference} from '../dist/formula-reference.js';
import {loadFormulaConfiguration} from '../dist/formula-loader.js';
test('reference fetch is lazy, single-flight and applies saved content',async()=>{
 let calls=0,resolve;
 const config=defaultFormulaConfiguration();config.groups[0].items[0].title='Nội dung đã lưu';
 globalThis.fetch=async(url,options)=>{calls++;assert.equal(url,'/api/v1/formula-reference');assert.equal(options.cache,'no-store');await new Promise(r=>resolve=r);return {ok:true,json:async()=>({configuration:config,version:2})};};
 assert.equal(calls,0);
 const first=loadFormulaConfiguration();const second=loadFormulaConfiguration();assert.equal(calls,1);assert.equal(first,second);
 resolve();assert.equal(await first,true);assert.match(renderFormulaReference(),/Nội dung đã lưu/);
 assert.equal(await loadFormulaConfiguration(),false);assert.equal(calls,1);
});
