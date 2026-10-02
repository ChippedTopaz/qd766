import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {buildUnitView,allUnitTotals,previousAvailablePeriod,snapshotForUnit} from "../dist/analytics.js";
import {buildAnalysisRows} from "../dist/csv-export.js";
const data=JSON.parse(readFileSync(new URL("../data/snapshots.json",import.meta.url)));
const [key,snap]=Object.entries(data.snapshots).find(([key])=>key.endsWith(":all"));
const id=key.slice(0,-4);
// Independent published total must be used consistently in dashboard/export.
snap.provinceAggregatedScore=61.86;snap.provinceAggregatedMaximum=100;
const view=buildUnitView(data,id,"all",data.province.id);
assert.equal(view.totalScore,61.86);assert.equal(view.totalMaximum,100);
assert.equal(buildAnalysisRows(view,snap,data.periods.find(p=>p.id===id),"Tỉnh","Tất cả","scores").at(-1)[9],61.86);
// A missing group must not turn a five-group sum into a complete total.
const partial=structuredClone(data);partial.snapshots[key].datasets.pop();
assert.equal(buildUnitView(partial,id,"all",data.province.id).totalScore,null);
assert.deepEqual(allUnitTotals(partial.snapshots[key]),[]);
// Missing child metrics do not erase the published child group score.
const child=snap.datasets[0].children[0];
if(child){
  const local=structuredClone(data);
  for(const dataset of local.snapshots[key].datasets)dataset.children=[{...child,metrics:[],parameters:{},apiScore:0,apiMaxScore:10}];
  local.units=[{...child}];
  const childView=buildUnitView(local,id,"all",child.departmentId);
  assert.equal(childView.totalScore,0);
  local.snapshots[key].delivery={capturedAt:"2026-10-02T09:00:00Z",detailsCapturedAt:"2026-09-28T09:00:00Z",summaryStale:false,detailsStale:true};
  const adjusted=snapshotForUnit(local.snapshots[key],child.departmentId);
  assert.equal(adjusted.delivery.capturedAt,"2026-09-28T09:00:00Z");
  assert.equal(adjusted.delivery.stale,true);
  assert.equal(local.snapshots[key].delivery.capturedAt,"2026-10-02T09:00:00Z");
  assert.equal(buildAnalysisRows(childView,local.snapshots[key],data.periods.find(p=>p.id===id),"Tỉnh","Tất cả","scores")[1][4],"2026-09-28T09:00:00Z");
}
const history=structuredClone(data);
history.periods=[
  {id:"m12",type:"month",year:2025,value:12},
  {id:"m1",type:"month",year:2026,value:1},
  {id:"m3",type:"month",year:2026,value:3},
  {id:"q4",type:"quarter",year:2025,value:4},
  {id:"q1",type:"quarter",year:2026,value:1},
  {id:"y25",type:"year",year:2025},
  {id:"y26",type:"year",year:2026},
];
history.snapshots=Object.fromEntries(history.periods.map(p=>[p.id+":all",snap]));
assert.equal(previousAvailablePeriod(history,"m1","all").id,"m12");
assert.equal(previousAvailablePeriod(history,"m3","all"),null);
assert.equal(previousAvailablePeriod(history,"q1","all").id,"q4");
assert.equal(previousAvailablePeriod(history,"y26","all").id,"y25");
assert.equal(previousAvailablePeriod(history,"m1","formality"),null);
console.log("ANALYTICS_INTEGRITY_OK: authoritative total/export, six-group completeness, zero vs missing, exact prior period");
