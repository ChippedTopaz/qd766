import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import ExcelJS from "exceljs";
import {buildLeadershipReport,buildLeadershipWorkbook} from "../dist/leadership-report.js";

const data=JSON.parse(readFileSync(new URL("../data/snapshots.json",import.meta.url)));
const [key,snapshot]=Object.entries(data.snapshots).find(([key])=>key.endsWith(":all"));
const period=data.periods.find(item=>key.startsWith(`${item.id}:`));
const root=data.province.id;
const benchmarks=Array.from({length:34},(_,index)=>({rootDepartmentId:index===0?root:`province-${index}`,provinceName:`Tỉnh ${index}`,totalScore:100-index,groups:Object.fromEntries(data.groupOrder.map(group=>[group,{score:index<2?10:9-index/10}])),capturedAt:"2026-10-02T09:00:00+07:00"}));
const report=buildLeadershipReport(data,period.id,"all",root,benchmarks);
assert.equal(report.rows.length,34);
assert.equal(report.groupLabels.length,6);
assert.equal(report.rows[0].id,root);
assert.deepEqual(report.rows.slice(0,3).map(row=>row.ranks[0]),[1,1,3]);
assert.equal(report.rows[0].total,100); // Province total remains authoritative, not a sum of rounded groups.
assert.ok(!report.notes.some(note=>note.includes("/34")));
const missing=structuredClone(benchmarks);missing[0].groups[data.groupOrder[0]].score=null;
const partial=buildLeadershipReport(data,period.id,"all",root,missing);
assert.equal(partial.rows.at(-1).total,null);assert.equal(partial.rows.at(-1).ranks[0],null);
assert.ok(buildLeadershipReport(data,period.id,"all",root,benchmarks.slice(0,3)).notes.some(note=>note.includes("3/34")));

// Synthetic agency rows exercise scope isolation and IDs absent in the first dataset.
const local=structuredClone(data);
const entity=snapshot.datasets[0].root;
local.units=[{departmentId:root,departmentName:"UBND tỉnh",departmentLevel:"PROVINCE_TOTAL"},
  {departmentId:"department-a",departmentName:"Sở A",departmentLevel:"PROVINCE"},
  {departmentId:"department-b",departmentName:"Sở B",departmentLevel:"PROVINCE"},
  {departmentId:"commune-a",departmentName:"UBND xã A",departmentLevel:"COMMUNE"}];
const localSnap=local.snapshots[key];
localSnap.datasets=data.groupOrder.map((group,index)=>({...snapshot.datasets[0],group,children:[
  {...entity,departmentId:"department-a",departmentName:"Sở A",departmentLevel:"PROVINCE",apiScore:0},
  {...entity,departmentId:"department-b",departmentName:"Sở B",departmentLevel:"PROVINCE",apiScore:index===0?null:10},
  {...entity,departmentId:"commune-a",departmentName:"UBND xã A",departmentLevel:"COMMUNE",apiScore:5},
  ...(index===1?[{...entity,departmentId:"department-c",departmentName:"Sở C",departmentLevel:"PROVINCE",apiScore:5}]:[])
]}));
const departments=buildLeadershipReport(local,period.id,"all","department-a",benchmarks);
assert.equal(departments.rows.length,3);assert.ok(departments.rows.every(row=>row.id.startsWith("department")));
assert.equal(departments.rows[0].total,0);assert.equal(departments.rows[0].totalRank,1);
assert.equal(departments.rows.find(row=>row.id==="department-b").total,null);
assert.equal(departments.rows.find(row=>row.id==="department-c").total,null);
const communes=buildLeadershipReport(local,period.id,"all","commune-a",benchmarks);
assert.equal(communes.rows.length,1);assert.equal(communes.rows[0].total,30);
const absent=structuredClone(local);delete absent.snapshots[key];
assert.ok(buildLeadershipReport(absent,period.id,"all","department-a",[]).rows.every(row=>row.total===null));

// Verify actual downloadable file roundtrip, numeric values, all groups and highlight.
await import("../vendor/exceljs/exceljs.min.js");
for(const WorkbookClass of [ExcelJS.Workbook,globalThis.ExcelJS.Workbook]){
  const workbook=buildLeadershipWorkbook(WorkbookClass,report);
  const buffer=await workbook.xlsx.writeBuffer();
  const reopened=new ExcelJS.Workbook();await reopened.xlsx.load(buffer);
  const sheet=reopened.worksheets[0];
  assert.equal(sheet.getRow(6).cellCount,15);assert.equal(sheet.getCell("O7").value,100);
  assert.deepEqual(sheet.getRow(6).values.slice(1),["STT",report.nameHeader,...report.groupLabels.flatMap(label=>[label,"Hạng"]),"Tổng điểm"]);
  for(const column of [4,6,8,10,12,14])assert.equal(sheet.getCell(6,column).value,"Hạng");
  assert.equal(sheet.getCell("C7").numFmt,"#,##0.00");assert.equal(sheet.getCell("D7").value,1);
  assert.equal(sheet.getCell("D7").font.color.argb,"FFB91C1C");
  assert.equal(sheet.getCell("B7").fill.fgColor.argb,"FF67CBE7");
  assert.equal(sheet.getRow(7).height,15);assert.deepEqual(sheet.model.merges,[]);
  assert.equal(sheet.getRow(6).height,sheet.getRow(7).height);
  sheet.getRow(6).eachCell(cell=>assert.notEqual(cell.alignment.wrapText,true));
  for(let column=1;column<=15;column++){
    const headerText=String(sheet.getCell(6,column).value);
    assert.ok(sheet.getColumn(column).width>=headerText.length+4);
  }
  assert.ok(sheet.getColumn(4).width<sheet.getColumn(3).width);
  assert.ok(sheet.getColumn(1).width<15); // Metadata does not stretch STT.
  assert.equal(sheet.views[0].ySplit,6);assert.equal(sheet.pageSetup.orientation,"landscape");
  for(const label of data.groupOrder.map(id=>data.groupLabels[id]))assert.ok(sheet.getRow(6).values.includes(label));
}
if(process.env.QD766_EXPORT_QA_DIR){
  await buildLeadershipWorkbook(ExcelJS.Workbook,report).xlsx.writeFile(`${process.env.QD766_EXPORT_QA_DIR}/leadership.xlsx`);
}
console.log("PASS leadership report: 34 provinces, agency/commune scopes, six groups, ties, null/zero, Excel + browser bundle roundtrip");
