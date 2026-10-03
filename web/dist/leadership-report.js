import { peerStats, snapshotKey } from "./analytics.js";
const numeric = (value) => typeof value === "number" && Number.isFinite(value) ? value : null;
const alphabet = new Intl.Collator("vi", { sensitivity: "base", numeric: true });
/** Read saved scores only. Missing values never contribute a zero to a total/rank. */
export function buildLeadershipReport(data, periodId, scope, selectedId, benchmarks) {
    const selected = data.units.find(item => item.departmentId === selectedId);
    const national = selected?.departmentLevel === "PROVINCE_TOTAL" || selectedId === data.province.id;
    const level = selected?.departmentLevel;
    const snap = data.snapshots[snapshotKey(periodId, scope, data.formality.id)];
    const report = { selectedId, selectedName: selected?.departmentName ?? data.province.name,
        period: data.periods.find(item => item.id === periodId)?.label ?? periodId,
        scope: scope === "all" ? "Tất cả thủ tục hành chính" : `${data.formality.code} · ${data.formality.name}`,
        population: national ? "34 tỉnh, thành phố" : `${level === "COMMUNE" ? "UBND xã, phường" : "Sở, ngành"} của ${data.province.name}`,
        nameHeader: national ? "Tỉnh/Thành phố" : "Cơ quan, đơn vị", groupLabels: data.groupOrder.map(id => data.groupLabels[id]), rows: [], capturedAt: [], notes: [] };
    if (national) {
        const unique = new Map(benchmarks.map(item => [item.rootDepartmentId, item]));
        report.rows = [...unique.values()].map(item => {
            const scores = data.groupOrder.map(id => numeric(item.groups[id]?.score));
            return { id: item.rootDepartmentId, name: item.provinceName, scores, ranks: [], total: scores.every(value => value !== null) ? numeric(item.totalScore) : null, totalRank: null };
        });
        report.capturedAt = [...unique.values()].map(item => item.capturedAt);
        if (report.rows.length !== 34)
            report.notes.push(`Có dữ liệu ${report.rows.length}/34 tỉnh, thành phố; thứ hạng chỉ tính trên các đơn vị có dữ liệu.`);
    }
    else if (level === "PROVINCE" || level === "COMMUNE") {
        const units = new Map(data.units.filter(item => item.departmentLevel === level).map(item => [item.departmentId, item.departmentName]));
        for (const dataset of snap?.datasets ?? [])
            for (const entity of dataset.children) {
                if (entity.departmentLevel === level)
                    units.set(entity.departmentId, entity.departmentName);
            }
        report.rows = [...units].map(([id, name]) => {
            const scores = data.groupOrder.map(group => numeric(snap?.datasets.find(dataset => dataset.group === group)?.children.find(entity => entity.departmentId === id)?.apiScore));
            return { id, name, scores, ranks: [], total: scores.every(value => value !== null) ? Number(scores.reduce((sum, value) => sum + value, 0).toFixed(2)) : null, totalRank: null };
        });
        report.capturedAt = (snap?.datasets ?? []).map(dataset => dataset.capture.capturedAt);
        if (snap?.delivery?.detailsStale || snap?.delivery?.stale)
            report.notes.push("Dữ liệu chi tiết đã quá hạn cập nhật.");
    }
    else
        report.notes.push("Chưa xác định được cấp cơ quan để lập danh sách so sánh.");
    report.capturedAt = [...new Set(report.capturedAt.filter(value => value && Number.isFinite(Date.parse(value))))].sort((a, b) => Date.parse(a) - Date.parse(b));
    for (const row of report.rows) {
        row.ranks = row.scores.map((score, index) => score === null ? null : peerStats(report.rows.flatMap(item => item.scores[index] === null || item.scores[index] === undefined ? [] : [item.scores[index]]), score)?.rank ?? null);
        row.totalRank = row.total === null ? null : peerStats(report.rows.flatMap(item => item.total === null ? [] : [item.total]), row.total)?.rank ?? null;
    }
    report.rows.sort((a, b) => a.total === null ? (b.total === null ? alphabet.compare(a.name, b.name) : 1) : b.total === null ? -1 : b.total - a.total || alphabet.compare(a.name, b.name));
    if (report.rows.some(row => row.total === null))
        report.notes.push("Ô trống là dữ liệu chưa có. Chỉ xếp hạng tổng điểm khi có đủ điểm của 6 nhóm; hạng từng nhóm tính trên các đơn vị có điểm nhóm đó.");
    if (report.rows.length && !report.rows.some(row => row.id === selectedId))
        report.notes.push("Chưa có cơ quan đang chọn trong dữ liệu so sánh.");
    if (report.capturedAt.length > 1)
        report.notes.push("Dữ liệu được cập nhật ở nhiều thời điểm, không phải một ảnh chụp đồng thời.");
    report.notes.push("Đồng điểm dùng thứ hạng 1, 2, 2, 4. Tổng điểm cấp tỉnh theo nguồn tổng hợp; tổng điểm đơn vị trực thuộc là tổng 6 nhóm.");
    report.notes.push("Nguồn: Cổng Dịch vụ công Quốc gia. Kỳ chưa kết thúc có thể tiếp tục thay đổi điểm.");
    return report;
}
export const leadershipColors = ["DBEAFE", "FFEDD5", "CFFAFE", "DCFCE7", "F3E8FF", "FEF3C7"];
export function leadershipUpdatedLabel(report) {
    const format = (value) => new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", dateStyle: "short", timeStyle: "short" }).format(new Date(value));
    const first = report.capturedAt[0], last = report.capturedAt.at(-1);
    return first ? `${format(first)}${last && last !== first ? ` đến ${format(last)}` : ""} (giờ Việt Nam)` : "Chưa có thời điểm cập nhật";
}
export function buildLeadershipWorkbook(WorkbookClass, report) {
    const workbook = new WorkbookClass();
    workbook.creator = "Phân tích QĐ766";
    const sheet = workbook.addWorksheet("Xếp hạng cùng cấp");
    sheet.properties.defaultRowHeight = 15;
    sheet.getCell("A1").value = "XẾP HẠNG ĐÁNH GIÁ CHẤT LƯỢNG PHỤC VỤ";
    sheet.getCell("A2").value = `${report.period} · ${report.population} · ${report.scope}`;
    sheet.getCell("A3").value = `Cập nhật: ${leadershipUpdatedLabel(report)}`;
    sheet.getCell("A4").value = `Cơ quan đang chọn: ${report.selectedName}`;
    for (let row = 1; row <= 4; row++) {
        sheet.getRow(row).height = 15;
        sheet.getCell(row, 1).font = { name: "Calibri", size: 11, bold: row === 1 };
    }
    const headers = ["STT", report.nameHeader, ...report.groupLabels.flatMap(label => [label, "Hạng"]), "Tổng điểm"];
    const header = sheet.getRow(6);
    header.values = headers;
    header.height = 15;
    header.eachCell((cell, col) => {
        const color = col >= 3 && col < headers.length ? leadershipColors[Math.floor((col - 3) / 2)] ?? "F1F5F9" : "F1F5F9";
        cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: `FF${color}` } };
        cell.font = { name: "Calibri", size: 10, bold: true };
        cell.alignment = { horizontal: "center", vertical: "middle", wrapText: false };
    });
    report.rows.forEach((item, index) => {
        const row = sheet.addRow([index + 1, item.name, ...item.scores.flatMap((score, i) => [score, item.ranks[i] ?? null]), item.total]);
        row.height = 15;
        row.eachCell({ includeEmpty: true }, (cell, col) => {
            cell.font = { name: "Calibri", size: 10, bold: col === headers.length || col > 3 && col % 2 === 0, color: { argb: col > 3 && col < headers.length && col % 2 === 0 ? "FFB91C1C" : "FF0F172A" } };
            cell.alignment = { horizontal: col === 2 ? "left" : "right", vertical: "middle", wrapText: false };
            cell.numFmt = col > 2 && (col === headers.length || col % 2 === 1) ? "#,##0.00" : "#,##0";
            if (item.id === report.selectedId)
                cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF67CBE7" } };
        });
    });
    for (let row = 6; row <= 6 + report.rows.length; row++)
        sheet.getRow(row).eachCell({ includeEmpty: true }, cell => {
            cell.border = { top: { style: "hair", color: { argb: "FFD1D5DB" } }, bottom: { style: "hair", color: { argb: "FFD1D5DB" } }, left: { style: "hair", color: { argb: "FFD1D5DB" } }, right: { style: "hair", color: { argb: "FFD1D5DB" } } };
        });
    const end = 6 + report.rows.length;
    // Fit table contents only: long report metadata/notes must not widen STT.
    const context = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
    headers.forEach((_, index) => {
        const column = index + 1;
        let width = 0;
        for (let row = 6; row <= end; row++) {
            const cell = sheet.getCell(row, column);
            const text = typeof cell.value === "number" ? cell.value.toLocaleString("vi-VN", {
                minimumFractionDigits: cell.numFmt === "#,##0.00" ? 2 : 0,
                maximumFractionDigits: cell.numFmt === "#,##0.00" ? 2 : 0,
            }) : String(cell.value ?? "").normalize("NFC");
            if (context)
                context.font = `${cell.font?.bold ? "bold " : ""}10pt Calibri`;
            width = Math.max(width, context ? context.measureText(text).width / 7 : text.length);
        }
        // Include whitespace and room for the header's filter arrow.
        sheet.getColumn(column).width = Math.min(255, Math.ceil(width + 4));
    });
    report.notes.forEach((note, index) => { const cell = sheet.getCell(end + 2 + index, 1); cell.value = note; cell.font = { name: "Calibri", size: 10, color: { argb: "FF64748B" } }; });
    sheet.autoFilter = { from: { row: 6, column: 1 }, to: { row: Math.max(6, end), column: headers.length } };
    sheet.views = [{ state: "frozen", xSplit: 2, ySplit: 6 }];
    sheet.pageSetup = { orientation: "landscape", paperSize: 9, fitToPage: true, fitToWidth: 1, fitToHeight: 0, printTitlesRow: "1:6", margins: { left: 0.25, right: 0.25, top: 0.3, bottom: 0.3, header: 0.1, footer: 0.1 } };
    return workbook;
}
//# sourceMappingURL=leadership-report.js.map