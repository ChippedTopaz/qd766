import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ExcelJS from 'exceljs';
import {applyRankingHistory,rankingTone,rankMovement,buildLeadershipWorkbook,renderRankingTable,sortRankingReport,nextRankingSort,rankingPeriodControl,resolveRankingPeriod} from '../dist/leadership-report.js';
const groups=['transparency','dvc-progress-tree'];
const report={selectedId:'a',selectedName:'A',period:'Năm 2026',scope:'Tất cả TTHC',population:'Cùng cấp',nameHeader:'Cơ quan, đơn vị',groupLabels:['Công khai','Tiến độ'],rows:[],capturedAt:[],notes:[]};
const day=(reportDate,values)=>({reportDate,capturedAt:reportDate+'T23:00:00Z',rows:values.map(([id,total,g])=>({id,name:id,total,groups:{transparency:g,'dvc-progress-tree':g}}))});
const current=day('2026-10-08',[['a',80,6],['b',75,5],['c',75,5],['d',60,2]]);
const baseline=day('2026-10-07',[['a',70,4],['b',85,7],['c',75,5],['d',60,2]]);
const ranked=applyRankingHistory(report,{current,baseline},groups);
assert.deepEqual(ranked.rows.map(r=>r.totalRank),[1,2,2,4]);
assert.equal(ranked.rows[0].totalRankChange,2);assert.equal(ranked.rows[0].totalChange,10);
assert.equal(ranked.rows[1].totalRankChange,-1);assert.equal(ranked.rows[1].totalChange,-10);
assert.equal(ranked.rows[3].totalRankChange,0);assert.equal(ranked.rows[3].totalChange,0);
assert.equal(ranked.reportDate,'2026-10-08');assert.match(ranked.comparisonLabel,/08\/10\/2026.*07\/10\/2026/);
assert.equal(rankingTone(1),'ranking-up');assert.equal(rankingTone(-1),'ranking-down');assert.equal(rankingTone(0),'ranking-neutral');assert.equal(rankingTone(null),'ranking-neutral');
assert.match(rankMovement(2),/▲ 2/);assert.match(rankMovement(-3),/▼ 3/);assert.match(rankMovement(0),/—/);assert.match(rankMovement(null),/—/);
for(const old of [null,{...baseline,reportDate:'2026-10-06'}]){
 const missing=applyRankingHistory(report,{current,baseline:old},groups);
 assert(missing.rows.every(r=>r.totalChange===null&&r.totalRankChange===null));
}
const changed=applyRankingHistory(report,{current,baseline:{...baseline,rows:baseline.rows.slice(0,3)}},groups);
assert.equal(changed.rows[0].totalRankChange,null);assert.equal(changed.rows[0].totalChange,10);
const incomplete=structuredClone(current);incomplete.rows[0].groups.transparency=null;
const partial=applyRankingHistory(report,{current:incomplete,baseline},groups);
assert.equal(partial.rows.find(r=>r.id==='a').total,null);assert.equal(partial.rows.find(r=>r.id==='a').ranks[0],null);
const empty=applyRankingHistory(report,{current:null,baseline:null},groups);assert.deepEqual(empty.rows,[]);
const before=JSON.stringify(report);applyRankingHistory(report,{current,baseline},groups);assert.equal(JSON.stringify(report),before);
const sortFixture={...ranked,rows:[
 {...ranked.rows[0],id:'low-total',total:60,scores:[5,null]},
 {...ranked.rows[1],id:'high-total',total:90,scores:[5,9]},
 {...ranked.rows[2],id:'low-score',total:99,scores:[2,1]},
 {...ranked.rows[3],id:'missing',total:100,scores:[null,null]},
]};
assert.deepEqual(sortRankingReport(sortFixture,{index:0,direction:'desc'}).rows.map(r=>r.id),['high-total','low-total','low-score','missing']);
assert.deepEqual(sortRankingReport(sortFixture,{index:0,direction:'asc'}).rows.map(r=>r.id),['low-score','high-total','low-total','missing']);
assert.equal(sortFixture.rows[0].id,'low-total','Sorting never mutates saved rows');
assert.equal(sortRankingReport(sortFixture,{index:99,direction:'asc'}),sortFixture);
const sortedHtml=renderRankingTable(sortRankingReport(ranked,{index:0,direction:'desc'}),groups);
assert.deepEqual(nextRankingSort(null,0),{index:0,direction:'desc'});
assert.deepEqual(nextRankingSort({index:0,direction:'desc'},1),{index:1,direction:'desc'});
assert.deepEqual(nextRankingSort({index:0,direction:'asc'},1),{index:1,direction:'desc'});
assert.deepEqual(nextRankingSort({index:1,direction:'desc'},1),{index:1,direction:'asc'});
assert.match(sortedHtml,/<th[^>]*data-ranking-sort="0"/,'Entire header cell responds to the first click');
assert.match(sortedHtml,/aria-sort="descending"/);assert.match(sortedHtml,/data-ranking-sort="0"/);
assert.match(renderRankingTable(sortRankingReport(ranked,{index:0,direction:'asc'}),groups),/aria-sort="ascending"/);
const sortedExport=buildLeadershipWorkbook(ExcelJS.Workbook,sortRankingReport(sortFixture,{index:0,direction:'asc'}));
assert.equal(sortedExport.worksheets[0].getCell('B7').value,sortFixture.rows[2].name);
const book=buildLeadershipWorkbook(ExcelJS.Workbook,ranked),sheet=book.worksheets[0];
assert.equal(sheet.getCell('A7').value,1);assert.equal(sheet.getCell('C7').value,80);
assert.equal(sheet.getCell('D7').font.color.argb,'FF047857');assert.equal(sheet.getCell('C8').font.color.argb,'FFB91C1C');assert.equal(sheet.getCell('C10').font.color.argb,'FF475569');assert.match(sheet.getCell('D7').note,/Tăng 2/);
assert.equal(sheet.getCell('D7').value,2);assert.match(sheet.getCell('D7').numFmt,/▲/);assert.equal(sheet.getCell('D10').value,0);
const app=readFileSync(new URL('../src/app.ts',import.meta.url),'utf8');
assert.doesNotMatch(app,/Báo cáo lãnh đạo/);assert.match(renderRankingTable(ranked,groups),/<th>Thứ hạng<\/th><th>Cơ quan, đơn vị<\/th><th>Tổng điểm<\/th>/);
assert.match(renderRankingTable(ranked,groups),/ranking-up/);assert.match(renderRankingTable(ranked,groups),/▲ 2/);
assert.match(renderRankingTable(ranked,groups),/<th>Tổng điểm<\/th><th>Tăng\/Giảm<\/th>/);
assert.equal((renderRankingTable(ranked,groups).match(/<th[^>]*>Hạng<\/th>/g)||[]).length,groups.length);
assert.equal((renderRankingTable(ranked,groups).match(/class="leadership-group-rank"/g)||[]).length,groups.length*ranked.rows.length);
assert.equal((renderRankingTable(ranked,groups).match(/ranking-movement/g)||[]).length,ranked.rows.length);
assert.doesNotMatch(renderRankingTable({...ranked,rows:[{...ranked.rows[0],name:'<script>bad</script>'}]},groups),/<script>/);
assert.match(app,/reportDate:report.reportDate\?\?rankingReportDay\(\)/);
const periods=[{id:'m9',type:'month',year:2026,value:9,label:'Tháng 9/2026'},{id:'m10',type:'month',year:2026,value:10,label:'Tháng 10/2026'},{id:'y',type:'year',year:2026,value:null,label:'Năm 2026'}];
const picker=rankingPeriodControl(periods,'m9');assert.match(picker,/data-ranking-period/);assert.match(picker,/<option value="m9" selected/);assert(picker.indexOf('value="m10"')<picker.indexOf('value="m9"'));
assert.match(picker,/Loại kỳ/);assert.match(picker,/Kỳ cụ thể/);assert.match(picker,/Năm của bảng xếp hạng/);assert.doesNotMatch(picker,/<optgroup/);
const reportPeriods=[...periods,{id:'m925',type:'month',year:2025,value:9,label:'Tháng 9/2025'},{id:'q4',type:'quarter',year:2026,value:4,label:'Quý 4/2026'}];
assert.equal(resolveRankingPeriod(reportPeriods,'m9','type','quarter'),'q4');
assert.equal(resolveRankingPeriod(reportPeriods,'m9','year','2025'),'m925');
assert.equal(resolveRankingPeriod(reportPeriods,'y','type','month'),'m10');
assert.equal(resolveRankingPeriod(reportPeriods,'m9','year','2000'),undefined);
assert.match(rankingPeriodControl(reportPeriods,'y'),/Cả năm/);
const t0=performance.now();const many=day('2026-10-08',Array.from({length:1500},(_,i)=>[String(i),i%100,i%10]));applyRankingHistory(report,{current:many,baseline:{...many,reportDate:'2026-10-07'}},groups);
assert(performance.now()-t0<2000,'Ranking should not recompute quantiles per cell');
const fullTable=renderRankingTable({...ranked,rows:Array.from({length:160},(_,i)=>({...ranked.rows[0],id:String(i),name:`Đơn vị ${i+1}`}))},groups);
assert.equal((fullTable.match(/<tr class=/g)||[]).length,160,'Compact styling must not hide or truncate units');
const css=readFileSync(new URL('../bento.css',import.meta.url),'utf8');
assert.match(css,/\.leadership-table tbody td\{padding:6px 8px;line-height:1\.35/);
console.log('RANKING_DAILY_PASS: ties, up/down/neutral, exact preceding day, missing/cohort guards, Excel, drilldown day, 1500 rows');
