import assert from 'node:assert/strict';
import {gauge,composition,trendChart} from '../dist/bento.js';
const ids=['transparency','dvc-progress-tree','provide-online-tree','dossier-digitized','handling-satisfaction','formality-online-payment-tree'];
const make=(total=61.89)=>({totalScore:total,groups:ids.map((id,i)=>({id,label:id,maximum:[18,20,12,22,18,10][i],score:{value:10}}))});
assert.match(gauge(61.89,100),/61,89/);
assert.match(gauge(null,100),/Chưa có tổng điểm/);
assert.match(gauge(0,100),/opacity="0"/);
assert.equal((composition(make()).match(/composition-label/g)||[]).length,6);
const missing=make();missing.groups[0].score.value=null;
assert.match(composition(missing),/Không tính cơ cấu từ dữ liệu thiếu/);
assert.match(trendChart([{label:'Tháng 1/2026',order:1,view:make()}],[]),/Chưa đủ lịch sử/);
const trend=trendChart([{label:'Tháng 1/2026',order:1,view:make(60)},{label:'Tháng 3/2026',order:3,view:make(62)}],[]);
assert.doesNotMatch(trend,/<path d="M[^" ]+ L[^" ]+" fill="none"/); // A missing month must break the line.
assert.match(trendChart([{label:'Tháng 1/2026',order:1,view:make(60)},{label:'Tháng 2/2026',order:2,view:make(62)}],['dvc-progress-tree']),/không phải tỷ lệ hồ sơ/);
console.log('BENTO_OK: authoritative gauge, null vs zero, six-group composition, truthful trend gaps');
