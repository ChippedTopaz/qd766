import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {onlineIndicators} from '../dist/online-indicators.js';
import {orderSatisfactionRows,detailMetricName} from '../dist/satisfaction-display-order.js';
const app=readFileSync(new URL('../dist/app.js',import.meta.url),'utf8');
const online=app.slice(app.indexOf('function onlineAnalysis('),app.indexOf('function progressDetail('));
const detail=app.slice(app.indexOf('function overviewGroupDetail('),app.indexOf('function miniTicket('));
const fixture=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
const source=Object.values(fixture.snapshots)[0].datasets.find(d=>d.group==='provide-online-tree').root;
const state={selectedGroup:'provide-online-tree',selectedMetric:null,scope:'all',unitId:'own',periodId:'month-test'};
const data={province:{id:source.departmentId,name:'Tỉnh mẫu'},units:[{departmentId:'own',departmentLevel:'COMMUNE'}]};
const entity={...source,departmentId:'own',apiScore:6,apiMaxScore:12,parameters:{},metrics:[]};
const dataset={root:{...source,parameters:{},apiScore:null},children:[],provinceOnlineParameters:source.parameters};
const view={id:'own',name:'Xã mẫu',groups:[{id:'provide-online-tree',label:'Dịch vụ công trực tuyến',entity,dataset}]};
const key=[data.province.id,state.periodId,state.scope,state.unitId].join(':');
const render=(mode)=>new Function('state','data','onlineIndicators','orderSatisfactionRows','detailMetricName','provinceOnlineViewKey','onlineProvinceKey','esc','n','int','pct','progressDetail','groupPeerComparison','rankFor','period','groupTableHeading','referenceNotice','groupComparisonSummary',online+detail+';return overviewGroupDetail;')(
 state,data,onlineIndicators,orderSatisfactionRows,detailMetricName,mode?key:null,()=>key,String,v=>v==null?'N/A':String(v),String,String,()=>null,()=>'<aside>Same agency comparison</aside>',()=>null,()=>({label:'Tháng thử nghiệm'}),(label,extra='')=>`<h3>${label}</h3>${extra}<button>Excel</button>`,()=>'',()=>''
)(view);
let html=render(false);
assert.match(html,/Xem điểm tỉnh/);assert.match(html,/Dữ liệu DVC trực tuyến hiện nay chỉ có dữ liệu chi tiết của tỉnh, chưa có dữ liệu chi tiết của cơ quan bạn/);
html=render(true);
assert.match(html,/Chi tiết DVC trực tuyến của Tỉnh mẫu/);assert.match(html,/Về điểm cơ quan/);
assert.match(html,/TTHC cung cấp DVCTT toàn trình/);assert.doesNotMatch(html,/toàn trình trong tổng TTHC|Tham số nguồn/);
assert.match(html,/<tfoot>[\s\S]*?<td class="num">6<\/td><td class="num">12<\/td><td class="num lost">6<\/td>/);
assert.equal(entity.apiScore,6);assert.deepEqual(entity.parameters,{});
delete dataset.provinceOnlineParameters;
assert.match(render(true),/Chưa có dữ liệu chi tiết DVC trực tuyến của tỉnh trong kỳ đã chọn/);
state.scope='formality';assert.doesNotMatch(render(false),/Xem điểm tỉnh/);
console.log('ONLINE_PROVINCE_REFERENCE_OK: provincial body, own score footer, safe missing data, all-scope only');
