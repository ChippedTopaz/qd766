import assert from 'node:assert/strict';
import {openScoreSimulator} from '../dist/score-simulator.js';
import {defaultFormulaConfiguration} from '../dist/formula-reference.js';
const config=defaultFormulaConfiguration();
config.groups.find(g=>g.id==='dossier-digitized').items.find(f=>f.id==='4.2').target=null;
const calls=[];
globalThis.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({configuration:config})}};
const nodes=new Map();
const control=s=>{if(!nodes.has(s))nodes.set(s,{value:'',innerHTML:'',textContent:'',handlers:{},removeAttribute(k){delete this[k]},addEventListener(k,fn){this.handlers[k]=fn}});return nodes.get(s)};
const body={innerHTML:'',textContent:'',querySelector:control};
let dialog;
globalThis.document={
 activeElement:null,querySelector:()=>null,
 body:{append(d){d.isConnected=true}},
 createElement(){dialog={className:'',innerHTML:'',isConnected:false,events:{},setAttribute(){},
  querySelector:s=>s==='[data-sim-body]'?body:control(s),
  showModal(){},addEventListener(k,fn){this.events[k]=fn},close(){this.events.close?.()},
  remove(){this.isConnected=false}};return dialog}
};
const entity={departmentName:'Xã mẫu',metrics:[{code:'SO_HOA_GIAY_TO_GIAI_QUYET',name:'Số hóa',numerator:20,denominator:100,apiScore:0.8,apiMaxScore:4}],parameters:{}};
const original=JSON.stringify(entity);
await openScoreSimulator('dossier-digitized','Số hóa hồ sơ',entity);
assert.match(body.innerHTML,/Chỉ tính thử/);
const output=control('[data-sim-result]'),extra=control('[data-sim-extra]'),desired=control('[data-sim-desired]');
extra.handlers.focus();assert.equal(extra.value,'');extra.handlers.blur();assert.equal(extra.value,'0');
extra.value='50';extra.handlers.input();
assert.match(output.innerHTML,/70 \/ 150/);assert.match(output.innerHTML,/46,67%/);assert.match(output.innerHTML,/1,87/);
assert.match(output.innerHTML,/<dt class="sim-green">Điểm giả lập<\/dt><dd class="sim-green">/);
assert.match(output.innerHTML,/<dt class="sim-green">Điểm tăng theo công thức<\/dt><dd class="sim-green">/);
extra.handlers.focus();assert.equal(extra.value,'50','Existing nonzero values must be preserved');
desired.value='2';desired.handlers.input();assert.equal(extra.value,'60');
desired.value='4';desired.handlers.input();assert.match(output.textContent,/Không thể đạt tuyệt đối/);
extra.value='-1';extra.handlers.input();assert.match(output.textContent,/số nguyên không âm/);
assert.equal(JSON.stringify(entity),original);
assert.equal(calls.length,1);assert.equal(calls[0].url,'/api/v1/formula-reference');assert.equal(calls[0].options.method,undefined);
control('[data-sim-close]').handlers.click();assert.equal(dialog.isConnected,false);
nodes.clear();
await openScoreSimulator('dossier-digitized','Số hóa hồ sơ',{parameters:{},metrics:[{code:'CITIZEN_DATA_CONNECTED_FORMALITY',name:'Kết nối dân cư',numerator:20,denominator:100,apiScore:0.4,apiMaxScore:2}]});
assert.match(control('[data-sim-growth-note]').textContent,/tổng số giữ nguyên/);
const fixedExtra=control('[data-sim-extra]');assert.equal(fixedExtra.max,'80');
fixedExtra.value='50';fixedExtra.handlers.input();
assert.match(control('[data-sim-result]').innerHTML,/70 \/ 100/);
assert.doesNotMatch(control('[data-sim-result]').innerHTML,/Không thể đạt tuyệt đối/);
control('[data-sim-desired]').value='2';control('[data-sim-desired]').handlers.input();
assert.equal(fixedExtra.value,'80');
control('[data-sim-close]').handlers.click();
console.log('SCORE_SIMULATOR_DIALOG_OK: saved configuration GET only, growth and target inputs, Vietnamese validation, modal close, no data/Credit mutation');
