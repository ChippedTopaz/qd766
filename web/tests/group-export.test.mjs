import assert from 'node:assert/strict';
import ExcelJS from 'exceljs';
import {buildGroupWorkbook,openGroupExport} from '../dist/group-export.js';
const ids=['transparency','dvc-progress-tree','provide-online-tree','dossier-digitized','handling-satisfaction','formality-online-payment-tree'];
const metric={code:'one',name:'Chỉ tiêu thử',numerator:0,denominator:1234,ratio:0,apiScore:0,apiMaxScore:6};
const units=[{departmentId:'a',departmentName:'UBND xã thử',departmentLevel:'COMMUNE'},{departmentId:'b',departmentName:'=1+1',departmentLevel:'PROVINCE'}];
const data={units,accessScope:'province',delivery:{capturedAt:'2026-10-04T04:00:00Z',detailsCapturedAt:'2026-10-03T01:00:00Z',detailsAvailable:true},groups:ids.map(id=>({id,label:id,capturedAt:'2026-10-03T01:00:00Z',entities:[{departmentId:'a',apiScore:0,apiMaxScore:18,apiRatio:0,scoreSource:'dvcqg-api',metrics:id==='provide-online-tree'?[]:[metric],parameters:{totalReceived:1234,scoreDelta:999,unknownTechnicalField:100}}]}))};
const context={name:'Tỉnh thử',period:'Năm 2026',scope:'Tất cả TTHC',snapshot:{datasets:[]}};
const original=JSON.stringify(data);
const workbook=buildGroupWorkbook(ExcelJS.Workbook,data,context);
assert.equal(JSON.stringify(data),original);
const loaded=new ExcelJS.Workbook();await loaded.xlsx.load(await workbook.xlsx.writeBuffer());
assert.equal(loaded.worksheets.length,6);
const first=loaded.worksheets[0];
assert.equal(first.rowCount,8);
assert.equal(first.getCell('D7').value,0);
assert.equal(first.getCell('D8').value,null);
assert.equal(first.getCell('G7').value,0);
assert.equal(first.getCell('H7').value,1234);
assert.equal(first.getCell('I7').value,0);
assert.equal(first.getCell('I7').numFmt,'0.00%');
assert.equal(first.getCell('B8').value,'=1+1');
assert.equal(first.views[0].xSplit,3);assert.equal(first.views[0].ySplit,6);
assert.equal(first.getCell('L6').value,'Điểm chưa đạt');
assert.equal(first.getCell('M6').value,'Tổng hồ sơ tiếp nhận');
for(const sheet of loaded.worksheets){
  const text=JSON.stringify(sheet.getSheetValues());assert.doesNotMatch(text,/scoreDelta|unknownTechnicalField|numerator/);
  assert(sheet.model.merges.every(range=>Number(range.match(/\d+$/)[0])<=6));
}
const restricted={...data,units:[units[0]],accessScope:'agency',groups:data.groups.map(group=>({...group,entities:group.entities.filter(entity=>entity.departmentId==='a')}))};
const own=buildGroupWorkbook(ExcelJS.Workbook,restricted,context);
for(const sheet of own.worksheets){assert.equal(sheet.rowCount,7);assert.doesNotMatch(JSON.stringify(sheet.getSheetValues()),/=1\+1/);}
const one=buildGroupWorkbook(ExcelJS.Workbook,{...restricted,groups:[restricted.groups[0]]},context);assert.equal(one.worksheets.length,1);
console.log('GROUP_EXPORT_OK: six/one sheet, strict input scope, zero/missing, numeric formats, freeze, no technical keys or formulas');

// Exercise the dialog without a login/session, network call or saving a test file.
class Element {
  listeners={};children=[];value='';textContent='';closed=false;removed=false;
  addEventListener(name,callback){this.listeners[name]=callback;}
  setAttribute(){}
  append(child){this.children.push(child);}
  remove(){this.removed=true;}
  showModal(){this.open=true;}
  close(){this.closed=true;this.open=false;this.listeners.close?.();}
  click(){this.clicked=true;}
  querySelector(selector){return this.fields[selector];}
}
let dialog,link,lastGroup,fail=false;
globalThis.document={body:new Element(),createElement(tag){
  const element=new Element();
  if(tag==='dialog'){
    dialog=element;element.fields=Object.fromEntries(['[data-context]','[data-scope]','[data-groups]','[data-status]','[data-download]'].map(key=>[key,new Element()]));
  }
  if(tag==='a')link=element;
  return element;
}};
globalThis.window={setTimeout(callback){callback();}};
globalThis.fetch=async url=>{
  lastGroup=new URL(url,'http://localhost').searchParams.get('group');
  return {ok:!fail,json:async()=>fail?{detail:'Lỗi thử nghiệm'}:{...restricted,groups:lastGroup==='all'?restricted.groups:restricted.groups.filter(group=>group.id===lastGroup)}};
};
const options={group:ids[0],groupLabel:'Công khai minh bạch',context,agency:true,query:new URLSearchParams({year:'2026'}),WorkbookClass:ExcelJS.Workbook};
for(const id of ['all',...ids]){
  openGroupExport({...options,defaultAll:true});
  const select=dialog.fields['[data-groups]'];
  assert.deepEqual(select.children.map(option=>option.value),['all',...ids]);
  assert.equal(select.value,'all');
  select.value=id;
  await dialog.fields['[data-download]'].listeners.click();
  assert.equal(lastGroup,id);
  assert.equal(link.clicked,true);
  assert.equal(dialog.closed,true);
  assert.equal(dialog.removed,true);
}
openGroupExport(options);
assert.equal(dialog.fields['[data-groups]'].value,ids[0]);
fail=true;
await dialog.fields['[data-download]'].listeners.click();
assert.equal(dialog.closed,false);
assert.equal(dialog.fields['[data-status]'].textContent,'Lỗi thử nghiệm');
assert.equal(dialog.fields['[data-download]'].disabled,false);
console.log('GROUP_EXPORT_DIALOG_OK: seven choices, selected group sent, close on download, stay open on error');
