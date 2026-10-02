import type { Workbook } from "exceljs";
import { buildAnalysisRows } from "./csv-export.js";
import type { PeriodOption, Snapshot, UnitView } from "./types.js";
import { parameterLabels } from "./parameter-labels.js";
import { snapshotForUnit } from "./analytics.js";

const vietnamDateParts = (value:string|Date) => {
  const date = new Date(value);
  if(Number.isNaN(date.getTime()))return null;
  const parts = new Intl.DateTimeFormat("en-GB",{
    timeZone:"Asia/Ho_Chi_Minh",year:"numeric",month:"2-digit",day:"2-digit",
    hour:"2-digit",minute:"2-digit",second:"2-digit",hourCycle:"h23",
  }).formatToParts(date);
  return Object.fromEntries(parts.map(part=>[part.type,part.value]));
};

function capturedAtFor(snapshot:Snapshot,kind:"scores"|"details"):string|null{
  if(kind==="details"&&snapshot.delivery?.detailsAvailable===false)return null;
  const detail = snapshot.delivery?.detailsCapturedAt;
  const summary = snapshot.delivery?.capturedAt;
  const fallback = snapshot.datasets.map(dataset=>dataset.capture.capturedAt).filter(value=>value&&!Number.isNaN(Date.parse(value))).sort((a,b)=>Date.parse(b)-Date.parse(a))[0];
  return (kind==="details"?detail??fallback??summary:summary??detail??fallback)??null;
}

export function analysisExcelFilename(name:string,snapshot:Snapshot,kind:"scores"|"details",exportedAt:Date=new Date()):string{
  const safeName = name.normalize("NFD").replace(/\p{M}/gu,"").replace(/đ/g,"d").replace(/Đ/g,"D")
    .replace(/[^a-zA-Z0-9]+/g,"-").replace(/^-|-$/g,"").slice(0,130).replace(/-$/g,"") || "Co-quan";
  const captured = capturedAtFor(snapshot,kind);
  const updated = captured?vietnamDateParts(captured):null;
  const exported = vietnamDateParts(exportedAt);
  if(!exported)throw new Error("Invalid export timestamp");
  const date = updated?`${updated.year}${updated.month}${updated.day}`:"chua-ro-ngay-cap-nhat";
  return `${safeName}-${date}-${kind==="scores"?"tonghop":"chitiet"}-${exported.year}${exported.month}${exported.day}-${exported.hour}${exported.minute}${exported.second}.xlsx`;
}

function displayTimestamp(value:string|null):string{
  const parts = value?vietnamDateParts(value):null;
  return parts?`${parts.day}/${parts.month}/${parts.year} ${parts.hour}:${parts.minute}`:"Chưa có thời điểm cập nhật";
}

export function buildAnalysisWorkbook(
  WorkbookClass: new () => Workbook,
  view:UnitView, snapshot:Snapshot, period:PeriodOption,
  province:string, scopeLabel:string, kind:"scores"|"details",
):Workbook{
  snapshot=snapshotForUnit(snapshot,view.id);
  const data = buildAnalysisRows(view,snapshot,period,province,scopeLabel,kind);
  const workbook = new WorkbookClass();
  workbook.creator = "Phân tích QĐ766";
  const sheet = workbook.addWorksheet(kind === "scores" ? "Điểm 6 nhóm" : "Số liệu thành phần");
  const headers = data[0]!.slice(8);
  const endColumn = headers.length;
  sheet.properties.defaultRowHeight = 15;
  sheet.getCell(1,1).value = kind === "scores" ? "BẢNG ĐIỂM BỘ CHỈ SỐ 766" : "SỐ LIỆU THÀNH PHẦN BỘ CHỈ SỐ 766";
  sheet.getCell(1,1).font = {name:"Calibri",size:11,bold:true,color:{argb:"FF1E3A8A"}};
  sheet.getCell(2,1).value = `Cơ quan, đơn vị: ${view.name}`;
  sheet.getCell(3,1).value = `Kỳ: ${period.label} | Phạm vi: ${scopeLabel}`;
  const freshness = snapshot.delivery?.stale ? "Dữ liệu quá hạn cập nhật" : period.provisional ? "Kỳ chưa kết thúc" : "Kỳ đã kết thúc";
  sheet.getCell(4,1).value = `Cập nhật điểm: ${displayTimestamp(capturedAtFor(snapshot,"scores"))} | Chi tiết: ${displayTimestamp(capturedAtFor(snapshot,"details"))} (giờ Việt Nam) | ${freshness}`;
  for(let row=1;row<=4;row++){
    sheet.getRow(row).height = 15;
    sheet.getCell(row,1).alignment = {horizontal:"left",vertical:"middle",wrapText:false};
    if(row>1)sheet.getCell(row,1).font = {name:"Calibri",size:11};
  }
  const headerRow = 6;
  sheet.getRow(headerRow).values = headers;
  sheet.getRow(headerRow).height = 15;
  sheet.getRow(headerRow).eachCell(cell=>{
    cell.font = {name:"Calibri",size:11,bold:true,color:{argb:"FFFFFFFF"}};
    cell.fill = {type:"pattern",pattern:"solid",fgColor:{argb:"FF1E3A8A"}};
    cell.alignment = {vertical:"middle",horizontal:"center",wrapText:false};
  });
  const integerHeaders = new Set(["Số lượng đạt","Tổng số","Thứ hạng","Số đơn vị so sánh"]);
  for(let index=1;index<data.length;index++){
    const row = sheet.getRow(headerRow+index);
    row.values = data[index]!.slice(8).map(value=>value === undefined ? null : value);
    row.height = 15;
    row.eachCell({includeEmpty:true},(cell,column)=>{
      cell.font = {name:"Calibri",size:11};
      cell.alignment = {vertical:"middle",wrapText:false,horizontal:typeof cell.value==="number"?"right":"left"};
      if(index%2===0)cell.fill = {type:"pattern",pattern:"solid",fgColor:{argb:"FFF8FAFC"}};
      if(typeof cell.value==="number"){
        const header = headers[column-1];
        const name = data[index]![10];
        const parameterDecimal = name === parameterLabels.averageScore || name === parameterLabels.avgProcessingDays;
        const integer = integerHeaders.has(String(header)) || (header === "Giá trị tham số" && Number.isInteger(cell.value) && !parameterDecimal);
        cell.numFmt = integer ? "#,##0" : "#,##0.00";
      }
    });
    if(kind==="scores"&&index===data.length-1){
      row.eachCell(cell=>{cell.font={name:"Calibri",size:11,bold:true};cell.fill={type:"pattern",pattern:"solid",fgColor:{argb:"FFDBEAFE"}}});
    }
  }
  headers.forEach((header,index)=>{
    // Fit business text and filter buttons; keep numeric columns compact.
    const longest = Math.max(String(header).length+3,...data.slice(1).map(row=>{
      const value = row[index+8];
      return typeof value === "string"?value.length+2:typeof value === "number"?value.toLocaleString("vi-VN",{maximumFractionDigits:2}).length+2:0;
    }));
    sheet.getColumn(index+1).width = Math.max(10,longest);
  });
  sheet.views = [{state:"frozen",ySplit:headerRow,showGridLines:false}];
  sheet.autoFilter = {from:{row:headerRow,column:1},to:{row:headerRow+data.length-1,column:endColumn}};
  sheet.pageSetup = {orientation:"landscape",paperSize:9,fitToPage:true,fitToWidth:1,fitToHeight:0,printTitlesRow:`${headerRow}:${headerRow}`};
  return workbook;
}
