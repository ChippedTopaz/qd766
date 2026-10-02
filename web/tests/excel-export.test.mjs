import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import ExcelJS from "exceljs";
import { buildUnitView } from "../dist/analytics.js";
import { analysisExcelFilename, buildAnalysisWorkbook } from "../dist/excel-export.js";
import { parameterLabels } from "../dist/parameter-labels.js";

const data = JSON.parse(readFileSync(new URL("../data/snapshots.json", import.meta.url)));
const [key, snapshot] = Object.entries(data.snapshots).find(([key])=>key.endsWith(":all"));
const period = data.periods.find(item=>key.startsWith(`${item.id}:`));
const view = buildUnitView(data,period.id,"all",data.province.id);
snapshot.delivery = {capturedAt:"2026-10-02T07:23:00+07:00",detailsCapturedAt:"2026-09-28T09:37:00+07:00",stale:true};
view.groups[0].entity.parameters = {scoreDelta:123,totalReceived:600057,averageScore:8,avgProcessingDays:2.91,totalOnTime:0};
view.groups[0].entity.metrics = [];

for(const kind of ["scores","details"]){
  const workbook = buildAnalysisWorkbook(ExcelJS.Workbook,view,snapshot,period,data.province.name,"Tất cả TTHC",kind);
  const buffer = await workbook.xlsx.writeBuffer();
  assert.equal(buffer[0],0x50);assert.equal(buffer[1],0x4b); // Real XLSX ZIP archive.
  const reopened = new ExcelJS.Workbook();
  await reopened.xlsx.load(buffer);
  const sheet = reopened.worksheets[0];
  assert.ok(sheet.getCell("A4").value.includes("Dữ liệu quá hạn cập nhật"));
  assert.ok(sheet.getCell("A4").value.includes("02/10/2026 07:23"));
  assert.equal(sheet.views[0].ySplit,6);
  assert.equal(sheet.properties.defaultRowHeight,15);
  assert.deepEqual(sheet.model.merges,[]);
  sheet.eachRow(row=>assert.equal(row.height,15));
  const rows=[];sheet.eachRow(row=>rows.push(row.values));
  const text=JSON.stringify(rows);
  assert.ok(!text.includes("scoreDelta"));assert.ok(!text.includes("Mã/trường"));
  if(kind==="details"){
    for(const name of ["Tổng hồ sơ tiếp nhận","Điểm đánh giá trung bình","Số ngày xử lý trung bình","Hồ sơ giải quyết đúng hạn"]){assert.ok(text.includes(name));}
    for(const key of Object.keys(parameterLabels)){assert.ok(!text.includes(`"${key}"`));}
    // Header metadata is separated from business rows. Find cells by contents.
    let countCell,averageCell,zeroCell;
    sheet.eachRow(row=>{
      if(row.getCell(1).value!==view.groups[0].label)return;
      if(row.getCell(3).value==="Tổng hồ sơ tiếp nhận")countCell=row.getCell(9);
      if(row.getCell(3).value==="Điểm đánh giá trung bình")averageCell=row.getCell(9);
      if(row.getCell(3).value==="Hồ sơ giải quyết đúng hạn")zeroCell=row.getCell(9);
    });
    assert.equal(countCell.value,600057);assert.equal(countCell.numFmt,"#,##0");
    assert.equal(averageCell.value,8);assert.equal(averageCell.numFmt,"#,##0.00");
    assert.equal(zeroCell.value,0);
    assert.equal(sheet.getCell("D7").value,null);
  }else{
    assert.equal(sheet.getCell("B7").value,view.groups[0].score.value);
    assert.equal(sheet.getCell("B7").numFmt,"#,##0.00");
  }
  if(process.env.QD766_EXPORT_QA_DIR){
    await mkdir(process.env.QD766_EXPORT_QA_DIR,{recursive:true});
    await workbook.xlsx.writeFile(`${process.env.QD766_EXPORT_QA_DIR}/${kind}.xlsx`);
  }
}
// Exercise the exact self-hosted browser build used by the download button.
await import("../vendor/exceljs/exceljs.min.js");
const browserBook=buildAnalysisWorkbook(globalThis.ExcelJS.Workbook,view,snapshot,period,data.province.name,"Tất cả TTHC","details");
const browserBytes=await browserBook.xlsx.writeBuffer();
const browserReadback=new ExcelJS.Workbook();
await browserReadback.xlsx.load(browserBytes);
assert.equal(browserReadback.worksheets[0].getCell("C7").value,"Tổng hồ sơ tiếp nhận");

const exportTime = new Date("2026-10-02T04:30:23Z");
assert.equal(analysisExcelFilename("UBND tỉnh Cà Mau",snapshot,"scores",exportTime),"UBND-tinh-Ca-Mau-20261002-tonghop-20261002-113023.xlsx");
assert.equal(analysisExcelFilename("UBND tỉnh Cà Mau",snapshot,"details",exportTime),"UBND-tinh-Ca-Mau-20260928-chitiet-20261002-113023.xlsx");
const boundary = structuredClone(snapshot);
boundary.delivery.detailsCapturedAt = "2026-10-01T18:30:00Z";
assert.ok(analysisExcelFilename('Cơ quan / "Đặc biệt"',boundary,"details",exportTime).startsWith("Co-quan-Dac-biet-20261002-chitiet-"));
console.log("EXCEL_EXPORT_OK (Node and browser bundle)");
