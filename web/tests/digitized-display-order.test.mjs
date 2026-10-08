import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {orderSatisfactionRows,detailMetricName} from '../dist/satisfaction-display-order.js';
const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const entity=Object.values(data.snapshots)[0].datasets.find(d=>d.group==='dossier-digitized').root;
const before=structuredClone(entity);
const rows=entity.metrics.map(metric=>({key:metric.code,metric}));
const ordered=orderSatisfactionRows('dossier-digitized',rows);
assert.deepEqual(ordered.map(row=>detailMetricName('dossier-digitized',row.metric)),[
 'Tỷ lệ hồ sơ TTHC có cấp kết quả giải quyết TTHC điện tử',
 'Tỷ lệ hồ sơ TTHC thực hiện số hóa hồ sơ',
 'Tỷ lệ hồ sơ khai thác, sử dụng lại thông tin, dữ liệu số hóa',
 'Tỷ lệ hồ sơ TTHC được số hóa có kết nối, chia sẻ dữ liệu phục vụ tái sử dụng',
 'Tỷ lệ TTHC triển khai kết nối, chia sẻ dữ liệu dân cư phục vụ giải quyết TTHC',
 'Tỷ lệ hồ sơ TTHC có sử dụng thông tin, dữ liệu dân cư',
 'Tỷ lệ cung cấp dịch vụ chứng thực bản sao điện tử từ bản chính',
]);
assert.deepEqual(entity,before);
for(const row of ordered)assert.equal(row.metric,entity.metrics.find(m=>m.code===row.key));
assert.deepEqual(orderSatisfactionRows('transparency',rows),rows);
assert.equal(detailMetricName('transparency',entity.metrics[0]),entity.metrics[0].name);
assert.equal(detailMetricName('dossier-digitized',{code:'UNKNOWN',name:'Chỉ tiêu mới'}),'Chỉ tiêu mới');
console.log('DIGITIZED_DISPLAY_OK: exact labels and order, source scores/formulas unchanged');
