import type { Workbook } from "exceljs";
import { buildAnalysisRows } from "./csv-export.js";
import type { PeriodOption, Snapshot, UnitView } from "./types.js";
import { parameterLabels } from "./parameter-labels.js";

export function buildAnalysisWorkbook(
  WorkbookClass: new () => Workbook,
  view:UnitView, snapshot:Snapshot, period:PeriodOption,
  province:string, scopeLabel:string, kind:"scores"|"details",
):Workbook{
  const data = buildAnalysisRows(view,snapshot,period,province,scopeLabel,kind);
  const workbook = new WorkbookClass();
  workbook.creator = "Phân tích QĐ766";
  const sheet = workbook.addWorksheet(kind === "scores" ? "Điểm 6 nhóm" : "Số liệu thành phần");
  const headers = data[0]!.slice(8);
  const endColumn = headers.length;
  sheet.mergeCells(1,1,1,endColumn);
  sheet.getCell(1,1).value = kind === "scores" ? "BẢNG ĐIỂM BỘ CHỈ SỐ 766" : "SỐ LIỆU THÀNH PHẦN BỘ CHỈ SỐ 766";
  sheet.getRow(1).height = 32;
  sheet.getCell(1,1).font = {name:"Calibri",size:16,bold:true,color:{argb:"FF1E3A8A"}};
  const context = data[1]?.slice(0,8) ?? [];
  const metadataLabels = data[0]!.slice(0,8);
  for(let i=0;i<metadataLabels.length;i++){
    const row = i + 2;
    sheet.getCell(row,1).value = metadataLabels[i] ?? "";
    let value = context[i];
    if(i === 6 && !value) value = snapshot.delivery?.stale === false ? "Trong ngưỡng cập nhật" : "Chưa có thông tin độ mới";
    sheet.mergeCells(row,2,row,endColumn);
    // Preserve Vietnam wall-clock time when Excel stores dates without timezone.
    if((i===4||i===5)&&typeof value === "string" && value && !Number.isNaN(Date.parse(value))){
      sheet.getCell(row,2).value = new Date(Date.parse(value)+7*60*60*1000);
      sheet.getCell(row,2).numFmt = 'dd/mm/yyyy hh:mm "(giờ Việt Nam)"';
    }else sheet.getCell(row,2).value = value ?? "";
    sheet.getCell(row,1).font = {name:"Calibri",size:11,bold:true};
    sheet.getCell(row,2).font = {name:"Calibri",size:11};
    sheet.getCell(row,2).alignment = {horizontal:"left",vertical:"middle",wrapText:true};
    sheet.getRow(row).height = i===1||i===3?32:24;
    sheet.getRow(row).alignment = {vertical:"middle",wrapText:true};
  }
  sheet.mergeCells(10,1,10,endColumn);
  sheet.getCell(10,1).value = "Nguồn: Cổng Dịch vụ công Quốc gia. Ô trống là giá trị chưa được cung cấp; số 0 là giá trị đã ghi nhận.";
  sheet.getCell(10,1).font = {name:"Calibri",size:10,color:{argb:"FF64748B"}};
  sheet.getCell(10,1).alignment = {wrapText:true,vertical:"middle"};
  sheet.getRow(10).height = 30;
  const headerRow = 12;
  sheet.getRow(headerRow).values = headers;
  sheet.getRow(headerRow).height = 36;
  sheet.getRow(headerRow).eachCell(cell=>{
    cell.font = {name:"Calibri",size:11,bold:true,color:{argb:"FFFFFFFF"}};
    cell.fill = {type:"pattern",pattern:"solid",fgColor:{argb:"FF1E3A8A"}};
    cell.alignment = {vertical:"middle",horizontal:"center",wrapText:true};
  });
  const integerHeaders = new Set(["Số lượng đạt","Tổng số","Thứ hạng","Số đơn vị so sánh"]);
  for(let index=1;index<data.length;index++){
    const row = sheet.getRow(headerRow+index);
    row.values = data[index]!.slice(8).map(value=>value === undefined ? null : value);
    row.height = kind==="scores"?30:46;
    row.eachCell({includeEmpty:true},(cell,column)=>{
      cell.font = {name:"Calibri",size:11};
      cell.alignment = {vertical:"middle",wrapText:true,horizontal:typeof cell.value==="number"?"right":"left"};
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
    sheet.getColumn(index+1).width = header==="Nhóm chỉ tiêu"?32:header==="Tên chỉ tiêu"?64:header==="Ghi chú"?60:header==="Trạng thái dữ liệu"?27:header==="Loại số liệu"?23:19;
  });
  sheet.views = [{state:"frozen",ySplit:headerRow,showGridLines:false}];
  sheet.autoFilter = {from:{row:headerRow,column:1},to:{row:headerRow+data.length-1,column:endColumn}};
  sheet.pageSetup = {orientation:"landscape",paperSize:9,fitToPage:true,fitToWidth:1,fitToHeight:0,printTitlesRow:"12:12"};
  return workbook;
}
