import assert from 'node:assert/strict';
import { formulaGroups, displayedFormulas, renderFormulaReference, referenceNotice } from '../dist/formula-reference.js';
import { analyzeOnlineScore } from '../dist/online-scoring.js';
import {readFileSync} from 'node:fs';
import {formulaMaximums,maximumText} from '../dist/formula-maximums.js';
import {formulaDocument} from '../dist/formula-document.js';
const items=formulaGroups.flatMap(g=>g.items);
assert.equal(formulaGroups.length,6);
assert.equal(formulaGroups.reduce((s,g)=>s+g.maximum,0),100);
assert.equal(items.length,21); // 20 document rows; 4.5 has two different ratios.
assert.equal(new Set(items.map(f=>f.id)).size,21);
const targets=Object.fromEntries(items.filter(f=>f.target).map(f=>[f.id,f.target]));
assert.deepEqual(targets,{'3.1':80,'3.3':50,'3.5':80,'4.2':80,'4.3':80,'5.4':90});
assert.match(items.find(f=>f.id==='3.3').multiplier,/hệ số đồng bộ/);
assert.match(items.find(f=>f.id==='3.6').caution,/mâu thuẫn đơn vị/);
assert.match(items.find(f=>f.id==='1.4').rules.join(' '),/12 tháng.*\/ 4/);
assert.match(items.find(f=>f.id==='2.2').rules.join(' '),/Giờ, Ngày, Ngày làm việc, tháng/);
assert.equal(items.find(f=>f.id==='3.2').target,undefined);
assert.equal(analyzeOnlineScore({apiScore:8.56,parameters:{authorityCount:89,partialCount:31,fullCount:21,onlineDossierCount:518,onlineServiceTotal:1881,channelOnlineSum:591643,channelTotalSum:600057}}),null);
const html=renderFormulaReference();
assert.equal((html.match(/class="formula-card"/g)||[]).length,4);
assert.equal((html.match(/data-formula-group=/g)||[]).length,6);
for(const group of formulaGroups){
  const selected=renderFormulaReference(group.id);
  assert.equal((selected.match(/class="formula-card"/g)||[]).length,displayedFormulas(group).length);
  for(const other of formulaGroups)assert.equal(selected.includes(`id="formula-${other.id}"`),other.id===group.id);
}
const source=JSON.parse(readFileSync(new URL('../../docs/metrics.m0.json',import.meta.url))).rows;
for(const group of formulaGroups){
 for(const row of formulaMaximums[group.id]){
  const original=source.find(item=>item.sourceRow===row.sourceRow);
  assert(original);
  assert.equal(row.maximum,original.maxScore);
  if(row.metricCode)assert.equal(row.metricCode,original.metricCode);
 }
 const output=renderFormulaReference(group.id);
 assert.doesNotMatch(output,/formula-maximums|<table|Điểm tối đa các chỉ tiêu thành phần/);
 assert.match(output,/Điểm tối đa:/);
}
for(const [group,total] of [['transparency',18],['dossier-digitized',22],['handling-satisfaction',18]]){
 assert.equal(formulaMaximums[group].reduce((sum,item)=>sum+(item.maximum??0),0),total);
}
assert.equal(maximumText(0),'0 điểm · Chỉ theo dõi');
assert.equal(maximumText(null),'Chưa xác định');
assert.doesNotMatch(renderFormulaReference('handling-satisfaction'),/Phản ánh, kiến nghị theo phân loại|Chỉ theo dõi/);
assert(html.indexOf('class="formula-index"')<html.indexOf('class="formula-guide"'));
assert.equal((html.match(/class="formula-guide"/g)||[]).length,1);
assert.doesNotMatch(html,/<details class="formula-guide" open|class="formula-intro"|class="formula-principles"/);
assert.match(renderFormulaReference('provide-online-tree'),/Điểm tối đa: Chưa xác định/);
assert.doesNotMatch(html,/Tài liệu chưa cung cấp điểm tối đa từng chỉ tiêu/);
const fixture=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
let observations=0;
for(const snapshot of Object.values(fixture.snapshots))for(const dataset of snapshot.datasets){
 for(const entity of [dataset.root,...dataset.children])for(const metric of entity.metrics){
  const known=formulaMaximums[dataset.group].find(row=>row.metricCode===metric.code);
  if(known&&metric.apiMaxScore!==null){assert.equal(known.maximum,metric.apiMaxScore);observations++;}
 }
}
assert(observations>0,'Known metric maximums must agree with captured API fixtures');
assert.match(html,/do quản trị viên cung cấp/);
assert.equal(formulaDocument.sha256,'41A27E55E251C616408D310EE7467CC831D373ED95B108FD65D5832A337087AF');
assert.equal(formulaDocument.records.length,20);
const escape=text=>text.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pages=formulaGroups.map(g=>renderFormulaReference(g.id)).join('');
for(const record of formulaDocument.records.filter(row=>row.id!=='5.1')){
 const formula=items.find(item=>item.id.replace(/[ab]$/,'')===record.id);
 const group=formulaGroups.find(g=>g.items.includes(formula));
 const page=renderFormulaReference(group.id);
 assert(page.includes(escape(record.title)),`Full source title missing: ${record.id}`);
 for(const line of record.business.filter(text=>text.trim())){
  assert(page.includes(escape(line.replace(/^=+|=+$/g,'').trim()))||page.includes(escape(line)),`Business rule lost: ${record.id}: ${line}`);
 }
 for(const line of record.notes){
  if(/^Chưa có thông tin/.test(line))assert.match(page,/Chưa có thông tin/);
  else assert(page.includes(escape(line)),`Source note lost: ${record.id}: ${line}`);
 }
 for(const line of record.dataSources)assert(page.includes(escape(line)),`Data source missing: ${record.id}`);
}
assert.equal((pages.match(/<h4>Mô tả nghiệp vụ<\/h4>/g)||[]).length,20);
assert.equal((pages.match(/<span>Lưu ý khi đánh giá<\/span>/g)||[]).length,20);
assert.equal((pages.match(/<span>Nguồn dữ liệu<\/span>/g)||[]).length,20);
assert.equal((pages.match(/formula-accordion-components" open/g)||[]).length,20);
assert.doesNotMatch(pages,/formula-accordion-(calculation|sources|notes)" open/);
assert.equal((html.match(/class="formula-group-maximum"/g)||[]).length,6);
assert.match(html,/<h3>[^<]+<\/h3><div class="formula-card-meta">/);
assert.match(html,/<dt>Tử số:<\/dt> <dd>/);
assert.match(html,/<dt>Mẫu số:<\/dt> <dd>/);
assert.match(renderFormulaReference('provide-online-tree'),/Ngưỡng đạt: 80%/);
assert.doesNotMatch(html,/điểm nhóm|công thức tra cứu|Điểm tối đa nhóm/);
for(const group of formulaGroups){
 assert(html.includes(`aria-label="${group.name}, tối đa ${group.maximum} điểm"`));
 assert(html.includes(`class="formula-group-maximum" aria-hidden="true">${group.maximum}</strong>`));
}
assert.match(renderFormulaReference('dvc-progress-tree'),/Điểm tối đa: 20 điểm/);
assert.doesNotMatch(renderFormulaReference('dvc-progress-tree'),/Điểm tối đa\/điểm tối đa riêng/);
assert.match(renderFormulaReference('provide-online-tree'),/nếu <i>R<\/i> ≥ 50%/);
assert.match(renderFormulaReference('provide-online-tree'),/Tỷ lệ toàn trình =/);
assert.match(renderFormulaReference('provide-online-tree'),/Tỷ lệ bưu chính =/);
assert.match(renderFormulaReference('dossier-digitized'),/DuocLayTuKhoDMQG = 1/);
assert.match(renderFormulaReference('handling-satisfaction'),/Dòng công thức trong tài liệu bị lỗi văn bản/);
const testRow=items[0].document;
const originalLine=testRow.business[0];
testRow.business[0]='<script>alert("x")</script>';
assert.doesNotMatch(renderFormulaReference(),/<script>/);
assert.match(renderFormulaReference(),/&lt;script&gt;/);
testRow.business[0]=originalLine;
assert.doesNotMatch(html,/<script|fetch\(/);
for(const group of formulaGroups){
 const link=referenceNotice(group.id);
 assert.match(link,new RegExp(`data-formula-group="${group.id}"`));
 assert.match(link,/<button type="button"/);
 assert.doesNotMatch(link,/<details|<summary|<p>/);
}
console.log('FORMULA_REFERENCE_OK: 6 groups, 21 ratios, exact thresholds, source ambiguities, no inferred online scores');
