// Office read-only check: GET saved PostgreSQL snapshots; no collection calls.
import assert from 'node:assert/strict';
import ExcelJS from 'exceljs';
import {buildUnitView,immediatePeers,snapshotKey} from '../web/dist/analytics.js';
import {buildAnalysisWorkbook} from '../web/dist/excel-export.js';
const base='http://127.0.0.1:8767/api/v1';
async function read(path){const response=await fetch(base+path,{signal:AbortSignal.timeout(20000)});assert(response.ok,`GET ${path}: ${response.status}`);return response.json();}
const provinces=await read('/dashboard/provinces');
const root=provinces.find(item=>item.name.includes('Phú Thọ'));assert(root);
const data=await read('/dashboard?root_department_id='+root.id);
const snapshots=Object.entries(data.snapshots).filter(([,snapshot])=>snapshot.scope==='formality');
assert(snapshots.length,'Existing TTHC snapshots required');
const checks=[];
for(const [oldKey,snapshot] of snapshots){
  const periodId=oldKey.split(':')[0],period=data.periods.find(item=>item.id===periodId);assert(period);
  const formality=await read('/formalities/'+snapshot.formalityId);
  data.formality={id:snapshot.formalityId,code:formality.code,name:formality.name};
  data.snapshots[snapshotKey(periodId,'formality',snapshot.formalityId)]=snapshot;
  const view=buildUnitView(data,periodId,'formality',root.id);
  assert.equal(snapshot.datasets.length,5,'TTHC scope has 5 supported groups, not 6 fabricated groups');
  const peers=immediatePeers(snapshot,root.id);assert(peers);
  for(const kind of ['scores','details']){
    const book=buildAnalysisWorkbook(ExcelJS.Workbook,view,snapshot,period,data.province.name,`${formality.code} · ${formality.name}`,kind);
    const copy=new ExcelJS.Workbook();await copy.xlsx.load(await book.xlsx.writeBuffer());
    assert(copy.worksheets[0].rowCount>6);
    assert(String(copy.worksheets[0].getCell(3,1).value).includes(formality.code));
  }
  checks.push({period:period.label,code:formality.code,groups:5,excel:'scores-and-details-readback-pass'});
}
console.log(JSON.stringify({state:'verified-read-only',province:data.province.name,checks}));
