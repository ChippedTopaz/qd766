import assert from 'node:assert/strict';
import {customComparisonTable} from '../dist/time-custom-comparison.js';
const groups=['transparency','dvc-progress-tree','provide-online-tree','dossier-digitized','handling-satisfaction','formality-online-payment-tree'];
const labels=Object.fromEntries(groups.map(g=>[g,g]));
for(const label of ['09/10/2026','Tháng 10/2026','Quý IV/2026','Năm 2026']){
 const html=customComparisonTable({label,total:72,rank:'3/34',groups:{transparency:0}},{label:'Mốc <script>',total:70,rank:'4/34',groups:{transparency:8}},groups,labels);
 const body=html.match(/<tbody>([\s\S]*)<\/tbody>/)[1];
 assert.equal((body.match(/<tr>/g)??[]).length,2);
 assert.equal((body.match(/<td/g)??[]).length,22);
 assert.match(body,/\+2,00/);assert.match(body,/0,00/);assert.match(body,/Mốc &lt;script&gt;/);
 assert.doesNotMatch(body,/<script>/);
}
const missing=customComparisonTable({label:'A',total:null,rank:'—',groups:{}},{label:'B',total:0,rank:'—',groups:{}},groups,labels);
assert.doesNotMatch(missing,/NaN|undefined|\+0,00/);
const reverse=customComparisonTable({label:'A',total:68,rank:'—',groups:{}},{label:'B',total:72,rank:'—',groups:{}},groups,labels);
assert.match(reverse,/-4,00/);assert.match(reverse,/change-negative/);
console.log('TIME_CUSTOM_COMPARISON_OK: four types, two rows, 11 columns, selected baseline, null/zero, HTML escaping');
for(const newerIsBaseline of [false,true]){
 const old={label:'Cũ',chronology:1,total:70,rank:'—',groups:{transparency:8,'dvc-progress-tree':15,'provide-online-tree':6,'dossier-digitized':null}};
 const recent={label:'Mới',chronology:2,total:72,rank:'—',groups:{transparency:10,'dvc-progress-tree':14,'provide-online-tree':6,'dossier-digitized':7}};
 const html=customComparisonTable(newerIsBaseline?old:recent,newerIsBaseline?recent:old,groups,labels);
 const rows=html.match(/<tbody>([\s\S]*)<\/tbody>/)[1].match(/<tr>[\s\S]*?<\/tr>/g);
 const latest=rows[newerIsBaseline?1:0],previous=rows[newerIsBaseline?0:1];
 assert.match(latest,/class="num change-positive">72,00/);
 assert.match(latest,/class="num change-positive">\+2,00/);
 assert.match(latest,/class="num change-positive">10,00/);
 assert.match(latest,/class="num change-negative">14,00/);
 assert.match(latest,/class="num change-neutral">6,00/);
 assert.match(latest,/class="num change-neutral">7,00/,'Missing comparison must not get red/green');
 assert.doesNotMatch(previous,/change-positive|change-negative/);
 recent.total=68;
 const decline=customComparisonTable(newerIsBaseline?old:recent,newerIsBaseline?recent:old,groups,labels);
 assert.match(decline,/class="num change-negative">68,00/);assert.match(decline,/-2,00/);
}
console.log('TIME_NEWER_COLORS_OK: either input order, total/six groups, growth/decline/zero/missing');
