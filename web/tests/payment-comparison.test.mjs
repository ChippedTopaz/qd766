import assert from 'node:assert/strict';
import {paymentRows,paymentComparisonPoint} from '../dist/payment-indicators.js';
const parameters={totalFeeDossierFormality:8,totalFeeFormality:40,totalDossierOnlineFormalityPaymentSuccess:18,totalFeeDossierFormalityDistinct:40,totalDossierOnlinePaymentSuccess:80,totalDossierFinancialObligation:100,
 agencyPaymentProvidedNumerator:8,agencyPaymentProvidedDenominator:40,agencyPaymentTransactionsNumerator:18,agencyPaymentTransactionsDenominator:40};
const keys=['payment:3.5','payment:3.5b','payment:3.6'];
for(const scope of ['all','formality']){
 const html=paymentRows(parameters,scope,'payment:3.5b').join('');
 for(const key of keys)assert.match(html,new RegExp('data-metric-detail="'+key.replace('.','\\.')+'"'));
 assert.equal((html.match(/class="row-link"/g)||[]).length,3);
 assert.match(html,/class="selectable-row selected" data-metric-detail="payment:3.5b"/);
 assert.deepEqual(keys.map(key=>paymentComparisonPoint({parameters},key,scope).score),[.5,1.13,4.8]);
 const peer={parameters:{},comparisonPoints:Object.fromEntries(keys.map((key,i)=>[key,{score:[.5,1.13,4.8][i],maximum:[2,2,6][i]}]))};
 assert.deepEqual(keys.map(key=>paymentComparisonPoint(peer,key,scope).score),[.5,1.13,4.8]);
 for(const key of keys)assert.match(paymentComparisonPoint(peer,key,scope).label,/Tỷ lệ/);
}
assert.equal(paymentComparisonPoint({parameters:{}},keys[0]),null);
assert.equal(paymentComparisonPoint({parameters},'payment:unknown'),null);
assert.doesNotMatch(paymentRows({}).join(''),/data-metric-detail/);
assert.equal(paymentComparisonPoint({parameters:{...parameters,totalFeeDossierFormality:0}},keys[0]).score,0);
console.log('PAYMENT_COMPARISON_PASS: clickable scored rows, selected highlight, correct labels/scores, score-only peers, all/formality, no missing-to-zero substitution');
