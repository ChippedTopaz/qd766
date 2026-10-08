import type { PeriodOption, Snapshot, UnitView } from "./types.js";
import { snapshotForUnit } from "./analytics.js";
import { parameterLabels } from "./parameter-labels.js";
import {detailExportEntries} from './detail-export.js';

type Cell = string | number | boolean | null | undefined;

/** UTF-8 BOM and semicolons work with Vietnamese Excel regional settings. */
export function encodeCsv(rows: Cell[][]): string {
  return "\uFEFF" + rows.map(row => row.map(value => {
    if (value === null || value === undefined) return '""';
    let text = typeof value === "number" ? String(value).replace(".", ",") : String(value);
    // Source names/parameters are untrusted; prevent spreadsheet formulas.
    if (typeof value === "string" && /^\s*[=+@-]/.test(text)) text = "'" + text;
    return '"' + text.replaceAll('"', '""') + '"';
  }).join(";")).join("\r\n") + "\r\n";
}

export function buildAnalysisRows(
  view: UnitView, snapshot: Snapshot, period: PeriodOption,
  province: string, scopeLabel: string, kind: "scores" | "details",
): Cell[][] {
  snapshot=snapshotForUnit(snapshot,view.id);
  const context: Cell[] = [province, view.name, period.label, scopeLabel,
    snapshot.delivery?.capturedAt ?? "", snapshot.delivery?.detailsCapturedAt ?? "",
    snapshot.delivery?.stale ? "Đã quá hạn cập nhật" : "",
    period.provisional ? "Kỳ chưa kết thúc" : "Kỳ đã kết thúc"];
  const headers = ["Tỉnh/thành phố", "Cơ quan, đơn vị", "Kỳ", "Phạm vi",
    "Cập nhật điểm", "Cập nhật chi tiết", "Độ mới dữ liệu", "Trạng thái kỳ"];
  if (kind === "scores") {
    const rows: Cell[][] = [[...headers, "Nhóm chỉ tiêu", "Điểm số", "Điểm tối đa",
      "Tỷ lệ điểm (%)", "Thứ hạng", "Số đơn vị so sánh", "Trung vị", "Trạng thái dữ liệu"]];
    for (const group of view.groups) {
      rows.push([...context, group.label, group.score.value, group.maximum, group.ratio,
        group.peer?.rank, group.peer?.total, group.peer?.median,
        group.score.kind === "UNSUPPORTED_SOURCE" ? "Nguồn không hỗ trợ" :
          group.score.value === null ? "Chưa có dữ liệu" : "Có dữ liệu"]);
    }
    rows.push([...context, "Tổng điểm", view.totalScore, view.totalMaximum, view.ratio,
      view.peer?.rank, view.peer?.total, view.peer?.median,
      view.totalScore === null ? "Chưa đủ dữ liệu" : "Có dữ liệu"]);
    return rows;
  }
  const rows: Cell[][] = [[...headers, "Nhóm chỉ tiêu", "Loại số liệu",
    "Tên chỉ tiêu", "Số lượng đạt", "Tổng số", "Tỷ lệ (%)", "Điểm ghi nhận/đối chiếu",
    "Điểm tối đa", "Giá trị tham số", "Ghi chú", "Điểm chưa đạt"]];
  for (const group of view.groups) {
    const entity = group.entity;
    const visibleParameters = entity ? Object.entries(entity.parameters).filter(([key])=>key!=="scoreDelta"&&Boolean(parameterLabels[key])) : [];
    if (!entity || (!entity.metrics.length && !visibleParameters.length)) {
      rows.push([...context, group.label, "Trạng thái", "", null, null, null,
        null, null, "", group.score.kind === "UNSUPPORTED_SOURCE" ?
          "Nguồn không hỗ trợ" : "Nguồn chưa cung cấp số liệu thành phần"]);
      continue;
    }
    for(const entry of detailExportEntries(group.id,entity,snapshot.scope)){
      if(entry.kind==='metric'){
        const m=entry.metric;
        rows.push([...context,group.label,'Chỉ tiêu',m.name,m.numerator,m.denominator,m.ratio,m.apiScore,m.apiMaxScore,'',entry.derived?'Điểm thành phần đối chiếu; điểm tổng giữ theo Cổng DVCQG':'Số liệu nguồn; ô trống không đồng nghĩa bằng 0',m.apiScore!==null&&m.apiMaxScore!==null?Math.round(Math.max(0,m.apiMaxScore-m.apiScore)*100)/100:null]);
      }else{
        const value=entry.value,scalar=value===null||typeof value==='number'||typeof value==='string'||typeof value==='boolean'?value:JSON.stringify(value);
        rows.push([...context,group.label,'Số liệu nghiệp vụ',entry.name,null,null,null,null,null,scalar,'Tham số gốc; chưa quy đổi thành điểm']);
      }
    }
  }
  return rows;
}

// Retained for internal CSV checks; user downloads use the Excel writer.
export function buildAnalysisCsv(view:UnitView,snapshot:Snapshot,period:PeriodOption,province:string,scopeLabel:string,kind:"scores"|"details"):string{
  return encodeCsv(buildAnalysisRows(view,snapshot,period,province,scopeLabel,kind));
}
