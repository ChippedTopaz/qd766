import type { PeriodOption, Snapshot, UnitView } from "./types.js";

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

export function buildAnalysisCsv(
  view: UnitView, snapshot: Snapshot, period: PeriodOption,
  province: string, scopeLabel: string, kind: "scores" | "details",
): string {
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
    return encodeCsv(rows);
  }
  const rows: Cell[][] = [[...headers, "Nhóm chỉ tiêu", "Loại số liệu", "Mã/trường",
    "Tên chỉ tiêu", "Số lượng đạt", "Tổng số", "Tỷ lệ (%)", "Điểm nguồn",
    "Điểm tối đa nguồn", "Giá trị tham số", "Ghi chú"]];
  for (const group of view.groups) {
    const entity = group.entity;
    if (!entity || (!entity.metrics.length && !Object.keys(entity.parameters).length)) {
      rows.push([...context, group.label, "Trạng thái", "", "", null, null, null,
        null, null, "", group.score.kind === "UNSUPPORTED_SOURCE" ?
          "Nguồn không hỗ trợ" : "Nguồn chưa cung cấp số liệu thành phần"]);
      continue;
    }
    for (const metric of entity.metrics) {
      rows.push([...context, group.label, "Chỉ tiêu", metric.code, metric.name,
        metric.numerator, metric.denominator, metric.ratio, metric.apiScore,
        metric.apiMaxScore, "", "Số liệu nguồn; ô trống không đồng nghĩa bằng 0"]);
    }
    for (const [key, value] of Object.entries(entity.parameters)) {
      const scalar = value === null || typeof value === "number" ||
        typeof value === "string" || typeof value === "boolean" ? value : JSON.stringify(value);
      rows.push([...context, group.label, "Tham số nguồn", key, "", null, null,
        null, null, null, scalar, "Tham số gốc; chưa quy đổi thành điểm"]);
    }
  }
  return encodeCsv(rows);
}
