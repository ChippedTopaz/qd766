import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {simulatedScore,requiredGrowth,simulationMetrics} from '../dist/score-simulator.js';
import {defaultFormulaConfiguration,setFormulaConfiguration} from '../dist/formula-reference.js';
const m={id:'4.2',name:'Số hóa',numerator:20,denominator:100,maximum:4,target:100,sourceScore:0.8};
assert.equal(simulatedScore(m,0).score,0.8);
const trial=simulatedScore(m,50);
assert.equal(trial.numerator,70);assert.equal(trial.denominator,150);
assert.equal(trial.ratio.toFixed(2),'46.67');assert.equal(trial.score.toFixed(2),'1.87');
assert.equal((trial.score-0.8).toFixed(2),'1.07');
assert.equal(requiredGrowth(m,2).extra,60);
assert.equal(requiredGrowth(m,4).extra,null);
assert.match(requiredGrowth(m,4).message,/Không thể đạt tuyệt đối/);
assert.equal(requiredGrowth({...m,numerator:100},4).extra,0);
for(const target of [80,90,100]){
 const metric={...m,target};
 for(const score of [0,0.4,1,2,3.5,4]){
  const r=requiredGrowth(metric,score);
  if(r.extra!==null){
   assert.ok(simulatedScore(metric,r.extra).score>=score);
   if(r.extra>0)assert.ok(simulatedScore(metric,r.extra-1).score<score);
  }
 }
}
assert.equal(requiredGrowth({...m,target:80},4).extra,300);
assert.equal(requiredGrowth({...m,target:90},4).extra,700);
assert.equal(simulatedScore({...m,target:80},300).score,4);
assert.equal(requiredGrowth(m,5).extra,null);
assert.throws(()=>simulatedScore(m,-1));assert.throws(()=>simulatedScore(m,0.5));
assert.throws(()=>simulatedScore(m,Number.MAX_SAFE_INTEGER));
const config=defaultFormulaConfiguration();
config.groups.find(g=>g.id==='dossier-digitized').items.find(f=>f.id==='4.2').target=null;
setFormulaConfiguration(config);
const entity={metrics:[{code:'SO_HOA_GIAY_TO_GIAI_QUYET',name:'Số hóa',numerator:20,denominator:100,apiScore:0.8,apiMaxScore:4}],parameters:{}};
const original=JSON.stringify(entity);
let items=simulationMetrics('dossier-digitized',entity);
assert.equal(items[0].target,100);assert.equal(items[0].maximum,4);
assert.equal(items[0].name,'Tỷ lệ hồ sơ TTHC thực hiện số hóa hồ sơ','Uses the detail table label, not the configured formula title');
assert.equal(JSON.stringify(entity),original,'No source mutation');
config.groups.find(g=>g.id==='dossier-digitized').items.find(f=>f.id==='4.2').target=90;
assert.equal(simulationMetrics('dossier-digitized',entity)[0].target,90,'Uses saved thresholds');
assert.deepEqual(simulationMetrics('dossier-digitized',{...entity,metrics:[{...entity.metrics[0],numerator:null}]}),[]);
assert.deepEqual(simulationMetrics('provide-online-tree',entity),[],'No fabricated online score components');
const transparency={parameters:{},metrics:[
 {code:'PUBLISH_ON_TIME',name:'Tỷ lệ TTHC công bố đúng hạn',numerator:0,denominator:0,apiScore:0,apiMaxScore:6},
 {code:'PUBLIC_UPDATE_ON_TIME',name:'Tỷ lệ TTHC cập nhật, công khai đúng hạn',numerator:0,denominator:0,apiScore:0,apiMaxScore:4},
 {code:'DOSSIER_SYNC',name:'Đồng bộ hồ sơ',numerator:0,denominator:0,apiScore:0,apiMaxScore:6},
]};
const zeroItems=simulationMetrics('transparency',transparency);
assert.equal(zeroItems.length,2,'Only the two requested zero-denominator indicators');
for(const item of zeroItems){
 assert.equal(simulatedScore(item,0).score,null);assert.equal(simulatedScore(item,0).ratio,null);
 assert.equal(simulatedScore(item,1).ratio,100);
 assert.equal(simulatedScore(item,1).score,item.maximum);
 assert.equal(requiredGrowth(item,item.maximum).extra,1);
}
const satisfaction={parameters:{},metrics:[{code:'DOSSIER_RECEIVING_SATISFACTION',name:'Tỷ lệ hài lòng trong tiếp nhận, giải quyết TTHC',numerator:355615,denominator:425866,apiScore:5.57,apiMaxScore:6}]};
const satisfied=simulationMetrics('handling-satisfaction',satisfaction);
assert.equal(satisfied.length,1,'5.4 uses the source numerator/denominator even with a complement reference expression');
assert.equal(satisfied[0].name,satisfaction.metrics[0].name);
assert.equal(simulatedScore(satisfied[0],0).score.toFixed(2),'5.57');
assert.deepEqual(simulationMetrics('handling-satisfaction',{...satisfaction,metrics:[{...satisfaction.metrics[0],numerator:null}]}),[]);
const fixed={...m,growthMode:'numerator-only'};
assert.equal(simulatedScore(fixed,50).denominator,100);
assert.equal(simulatedScore(fixed,50).numerator,70);
assert.equal(simulatedScore(fixed,50).score,2.8);
assert.equal(requiredGrowth(fixed,4).extra,80);
assert.equal(requiredGrowth({...fixed,target:80},4).extra,60);
assert.equal(requiredGrowth({...fixed,target:90},4).extra,70);
assert.throws(()=>simulatedScore(fixed,81),/không được vượt tổng số/);
const connected=simulationMetrics('dossier-digitized',{parameters:{},metrics:[{code:'CITIZEN_DATA_CONNECTED_FORMALITY',name:'Kết nối',numerator:20,denominator:100,apiScore:0.4,apiMaxScore:2}]});
assert.equal(connected[0].growthMode,'numerator-only');
const payments=simulationMetrics('formality-online-payment-tree',{metrics:[],parameters:{
 totalFeeDossierFormality:20,totalFeeFormality:100,totalDossierOnlineFormalityPaymentSuccess:20,totalFeeDossierFormalityDistinct:100,totalDossierOnlinePaymentSuccess:20,totalDossierFinancialObligation:100
}});
assert.deepEqual(payments.map(p=>p.growthMode),['numerator-only','numerator-only','both']);
for(const p of payments.slice(0,2)){
 assert.equal(simulatedScore(p,50).denominator,100);
 assert.equal(requiredGrowth(p,p.maximum).extra,60);
}
assert.equal(simulatedScore(payments[2],50).denominator,150,'Payment dossier indicator retains the original rule');
const app=readFileSync(new URL('../src/app.ts',import.meta.url),'utf8');
assert.doesNotMatch(app,/Xem lại 6 nhóm/);
assert.ok(app.indexOf('data-score-simulator>Giả lập')<app.indexOf('data-group-export>Tải biểu Excel'));
const module=readFileSync(new URL('../src/score-simulator.ts',import.meta.url),'utf8');
assert.doesNotMatch(module,/method:\s*['"]POST|localStorage|api\/v1\/me/,'Read-only simulation');
console.log('SCORE_SIMULATOR_OK: 70/150, 1.87, inverse minimal integers, 80/90/100 thresholds, unreachable maximum, saved config, source immutability and button placement');
