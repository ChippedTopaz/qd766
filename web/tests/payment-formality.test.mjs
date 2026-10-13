import assert from 'node:assert/strict';
import ExcelJS from 'exceljs';
import {paymentIndicators,paymentRows} from '../dist/payment-indicators.js';
import {detailExportEntries} from '../dist/detail-export.js';
import {buildGroupWorkbook} from '../dist/group-export.js';
const parameters={totalFeeDossierFormality:1,totalFeeFormality:1,totalDossierOnlineFormalityPaymentSuccess:1,totalFeeDossierFormalityDistinct:1,totalDossierOnlinePaymentSuccess:80,totalDossierFinancialObligation:100,
 agencyPaymentProvidedNumerator:8,agencyPaymentProvidedDenominator:40,agencyPaymentTransactionsNumerator:18,agencyPaymentTransactionsDenominator:40};
const before=JSON.stringify(parameters),indicators=paymentIndicators(parameters,'formality');
assert.deepEqual(indicators.map(d=>d.score),[.5,1.13,4.8]);
for(const d of indicators.slice(0,2))assert.deepEqual([d.numerator,d.denominator,d.ratio],[null,null,null]);
assert.equal(indicators[2].ratio,80);assert.equal(JSON.stringify(parameters),before);
for(const html of paymentRows(parameters,'formality').slice(0,2))assert.equal((html.match(/>N\/A</g)||[]).length,3);
assert.deepEqual(paymentIndicators(parameters).map(d=>d.score),[2,2,4.8],'All-TTHC display unchanged');
assert.deepEqual(paymentIndicators({totalFeeFormality:1,totalFeeDossierFormality:1},'formality').map(d=>d.score),[null,null,null],'Do not substitute procedure or missing reference scores');
const entity={departmentId:'own',apiScore:8.8,apiMaxScore:10,apiRatio:88,metrics:[],parameters};
assert.deepEqual(detailExportEntries('formality-online-payment-tree',entity,'formality').map(e=>e.metric.apiScore),[.5,1.13,4.8]);
const book=buildGroupWorkbook(ExcelJS.Workbook,{units:[{departmentId:'own',departmentName:'Cơ quan',departmentLevel:'COMMUNE'}],groups:[{id:'formality-online-payment-tree',label:'Thanh toán',entities:[entity]}],accessScope:'agency'},
 {name:'Cơ quan',period:'Tháng 10',scope:'TTHC cụ thể',snapshot:{scope:'formality'}});
const reopened=new ExcelJS.Workbook();await reopened.xlsx.load(await book.xlsx.writeBuffer());const sheet=reopened.worksheets[0];
assert.deepEqual(['G7','H7','I7','M7','N7','O7'].map(c=>sheet.getCell(c).value),Array(6).fill('N/A'));
assert.deepEqual(['J7','P7','V7'].map(c=>sheet.getCell(c).value),[.5,1.13,4.8]);assert.equal(sheet.getCell('D7').value,8.8,'Group source score unchanged');
console.log('PAYMENT_FORMALITY_PASS: N/A counts, same-agency general scores, dossier ratio retained, Excel parity, no mutations');
