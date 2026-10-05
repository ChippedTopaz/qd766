import assert from 'node:assert/strict';
import {renderCollectionReport,collectionPeriod} from '../dist/admin-collection.js';
assert.equal(collectionPeriod({type:'month',year:2026,month:9}),'Tháng 9/2026');
const report={counts:{queued:2,succeeded:3},total:1,offset:0,limit:30,localSimulation:true,
 control:{state:'open',reason:'operator-requested-pause'},
 jobs:[{id:'job-id',state:'queued',kind:'formality',province:'<script>bad</script>',period:{type:'month',year:2026,month:9},
 formalityId:'id',requestedBy:['Người A','Người B'],formalityName:'Thủ tục mẫu',attempts:0,expectedGroups:5,
 createdAt:'2026-10-05T00:00:00Z',updatedAt:'2026-10-05T00:00:00Z',nextRunAt:null,errorKind:null}],
 batches:[],probe:{label:'Đợt kiểm chứng dữ liệu thật',state:'COMPLETE',phases:[{period:'month-2026-9',total:34,counts:{SUCCESS:34}}],errors:[]}};
const html=renderCollectionReport(report);
assert.ok(html.includes('Tạm dừng'));
assert.ok(html.includes('34 / 34'));
assert.ok(html.includes('Người A, Người B'));
assert.ok(html.includes('Thủ tục mẫu'));
assert.ok(html.includes('&lt;script&gt;'));
assert.ok(!html.includes('<script>bad'));
assert.ok(html.includes('môi trường mô phỏng'));
assert.ok(!html.includes('Tạo job'));
console.log('ADMIN_COLLECTION_RENDER_PASS');
