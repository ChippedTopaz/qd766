import { snapshotKey } from "./analytics.js";
export function nextRankingSort(current, index) {
    return { index, direction: current?.index === index && current.direction === 'desc' ? 'asc' : 'desc' };
}
export function sortRankingReport(report, sort) {
    if (!sort || !Number.isInteger(sort.index) || sort.index < 0 || sort.index >= report.groupLabels.length)
        return report;
    const rows = [...report.rows].sort((a, b) => {
        const left = a.scores[sort.index], right = b.scores[sort.index];
        if (left == null || right == null) {
            if (left != null)
                return -1;
            if (right != null)
                return 1;
        }
        else if (left !== right)
            return sort.direction === 'desc' ? right - left : left - right;
        if (a.total != null && b.total != null && a.total !== b.total)
            return b.total - a.total;
        if (a.total != null && b.total == null)
            return -1;
        if (a.total == null && b.total != null)
            return 1;
        return alphabet.compare(a.name, b.name) || a.id.localeCompare(b.id);
    });
    return { ...report, rows, sort };
}
export function previousRankingPeriod(periods, id) {
    const current = periods.find(p => p.id === id);
    if (!current || current.type === 'year')
        return undefined;
    const scale = current.type === 'month' ? 12 : 4;
    return periods.find(p => p.type === current.type && p.year * scale + (p.value ?? 0) === current.year * scale + (current.value ?? 0) - 1);
}
/** Compare saved adjacent periods, independently of daily observation versions. */
export function applyRankingPeriod(report, baseline) {
    const ids = (rows) => rows.filter(r => r.total !== null).map(r => r.id).sort().join('|');
    const same = ids(report.rows) === ids(baseline.rows);
    const prior = new Map(baseline.rows.map(r => [r.id, r]));
    return { ...report, comparisonLabel: `So với ${baseline.period}`, rows: report.rows.map(row => {
            const old = prior.get(row.id);
            return { ...row, totalChange: row.total !== null && old?.total != null ? Number((row.total - old.total).toFixed(2)) : null,
                totalRankChange: same && row.totalRank !== null && old?.totalRank != null ? old.totalRank - row.totalRank : null,
                scoreChanges: row.scores.map((value, i) => value !== null && old?.scores[i] != null ? Number((value - old.scores[i]).toFixed(2)) : null) };
        }), notes: [...report.notes, ...(!same ? ['Tập đơn vị có đủ dữ liệu đã thay đổi; không tính biến động thứ hạng tổng điểm.'] : [])] };
}
const numeric = (value) => typeof value === "number" && Number.isFinite(value) ? value : null;
const alphabet = new Intl.Collator("vi", { sensitivity: "base", numeric: true });
function assignRanks(rows, count) {
    const ranked = (values) => {
        const sorted = values.filter((v) => v !== null).sort((a, b) => a - b);
        return (value) => {
            if (value === null)
                return null;
            let low = 0, high = sorted.length;
            while (low < high) {
                const middle = (low + high) >>> 1;
                if (sorted[middle] > value + .005)
                    high = middle;
                else
                    low = middle + 1;
            }
            return 1 + sorted.length - low;
        };
    };
    const totalRank = ranked(rows.map(r => r.total)), groupRanks = Array.from({ length: count }, (_, i) => ranked(rows.map(r => r.scores[i] ?? null)));
    for (const row of rows) {
        row.totalRank = totalRank(row.total);
        row.ranks = groupRanks.map((rank, i) => rank(row.scores[i] ?? null));
    }
}
/** Saved same-year daily scores only; never substitute the last available day for yesterday. */
export function applyRankingHistory(report, history, groups) {
    if (!history.current)
        return { ...report, notes: [...report.notes, 'Chưa có bản lưu theo ngày để đối chiếu biến động.'] };
    const current = history.current, baseline = history.baseline;
    const rowsFor = (day) => {
        const rows = day.rows.map(row => ({ id: row.id, name: row.name, total: numeric(row.total), totalRank: null,
            scores: groups.map(g => numeric(row.groups[g])), ranks: [] }));
        for (const row of rows)
            if (row.scores.some(score => score === null))
                row.total = null;
        assignRanks(rows, groups.length);
        return rows;
    };
    const rows = rowsFor(current), prior = baseline ? rowsFor(baseline) : [];
    const preceding = new Date(Date.parse(current.reportDate + 'T00:00:00Z') - 86400000).toISOString().slice(0, 10);
    const valid = baseline?.reportDate === preceding;
    const cohort = (items, index) => items.filter(row => index === null ? row.total !== null : row.scores[index] != null).map(row => row.id).sort().join('|');
    const same = valid && cohort(rows, null) === cohort(prior, null);
    const sameGroups = groups.map((_, i) => valid && cohort(rows, i) === cohort(prior, i));
    const priorById = new Map(prior.map(row => [row.id, row]));
    for (const row of rows) {
        const old = valid ? priorById.get(row.id) : undefined;
        row.totalChange = row.total !== null && old?.total != null ? Number((row.total - old.total).toFixed(2)) : null;
        row.totalRankChange = same && row.totalRank !== null && old?.totalRank != null ? old.totalRank - row.totalRank : null;
        row.scoreChanges = row.scores.map((score, i) => score !== null && old?.scores[i] != null ? Number((score - old.scores[i]).toFixed(2)) : null);
        row.rankChanges = row.ranks.map((rank, i) => sameGroups[i] && rank !== null && old?.ranks[i] != null ? old.ranks[i] - rank : null);
    }
    rows.sort((a, b) => a.total === null ? (b.total === null ? alphabet.compare(a.name, b.name) : 1) : b.total === null ? -1 : b.total - a.total || alphabet.compare(a.name, b.name));
    const day = (value) => value.split('-').reverse().join('/');
    return { ...report, rows, capturedAt: [current.capturedAt], reportDate: current.reportDate, comparisonLabel: `Dữ liệu ngày ${day(current.reportDate)} · So với ngày ${day(preceding)}`,
        notes: [...report.notes, ...(!valid ? ['Chưa có dữ liệu ngày liền trước; không tính biến động.'] : !same ? ['Tập đơn vị có đủ dữ liệu đã thay đổi; không tính biến động thứ hạng tổng điểm.'] : [])] };
}
export function rankingTone(change) {
    return change == null ? 'ranking-neutral' : Math.abs(change) < .005 ? 'ranking-neutral' : change > 0 ? 'ranking-up' : 'ranking-down';
}
export function rankMovement(value) {
    const label = value == null ? 'Chưa có dữ liệu so sánh' : value === 0 ? 'Thứ hạng không đổi' : `${value > 0 ? 'Tăng' : 'Giảm'} ${Math.abs(value)} bậc`;
    return `<span class="ranking-movement" title="${label}" aria-label="${label}">${value == null || value === 0 ? '—' : `${value > 0 ? '▲' : '▼'} ${Math.abs(value)}`}</span>`;
}
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
    assignRanks(report.rows, data.groupOrder.length);
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
const escapeRanking = (value) => value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export function rankingPeriodControl(periods, selectedId) {
    const selected = periods.find(p => p.id === selectedId);
    if (!selected)
        return '';
    const items = periods.filter(p => p.type === selected.type && p.year === selected.year).sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
    const years = [...new Set(periods.filter(p => p.type === selected.type).map(p => p.year))].sort((a, b) => b - a);
    return `<div class="ranking-period-control" role="group" aria-label="Kỳ báo cáo của bảng xếp hạng"><label><span>Loại kỳ</span><select data-ranking-period-field="type" aria-label="Loại kỳ của bảng xếp hạng">${['month', 'quarter', 'year'].filter(type => periods.some(p => p.type === type)).map(type => `<option value="${type}" ${type === selected.type ? 'selected' : ''}>${type === 'month' ? 'Tháng' : type === 'quarter' ? 'Quý' : 'Năm'}</option>`).join('')}</select></label><label><span>Kỳ cụ thể</span><select data-ranking-period aria-label="Kỳ cụ thể của bảng xếp hạng">${items.map(p => `<option value="${escapeRanking(p.id)}" ${p.id === selectedId ? 'selected' : ''}>${p.type === 'year' ? 'Cả năm' : `${p.type === 'month' ? 'Tháng' : 'Quý'} ${p.value}`}</option>`).join('')}</select></label><label><span>Năm</span><select data-ranking-period-field="year" aria-label="Năm của bảng xếp hạng">${years.map(year => `<option value="${year}" ${year === selected.year ? 'selected' : ''}>${year}</option>`).join('')}</select></label></div>`;
}
export function resolveRankingPeriod(periods, selectedId, field, value) {
    const selected = periods.find(p => p.id === selectedId);
    if (!selected)
        return;
    const candidates = periods.filter(p => field === 'type' ? p.type === value : p.type === selected.type && p.year === Number(value));
    candidates.sort((a, b) => b.year - a.year || (b.value ?? 0) - (a.value ?? 0));
    return (candidates.find(p => p.year === selected.year && p.value === selected.value) ??
        candidates.find(p => field === 'type' ? p.year === selected.year : p.value === selected.value) ?? candidates[0])?.id;
}
export function renderRankingTable(report, groups, point = (value) => value === null ? '—' : value.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }), nameLink = (_id, name) => escapeRanking(name)) {
    return `<div class="ranking-scroll"><table class="leadership-table"><thead><tr><th>Thứ hạng</th><th>${escapeRanking(report.nameHeader)}</th><th>Tổng điểm</th><th>Tăng/Giảm</th>${report.groupLabels.map((label, index) => `<th style="background:#${leadershipColors[index]}" data-ranking-sort="${index}" aria-sort="${report.sort?.index === index ? (report.sort.direction === 'desc' ? 'descending' : 'ascending') : 'none'}"><button type="button" class="ranking-sort" title="Sắp xếp theo ${escapeRanking(label)}">${escapeRanking(label)}<span aria-hidden="true">${report.sort?.index === index ? (report.sort.direction === 'desc' ? '▾' : '▴') : '↕'}</span></button></th><th style="background:#${leadershipColors[index]}">Hạng</th>`).join("")}</tr></thead><tbody>${report.rows.map((row) => `<tr class="${row.id === report.selectedId ? "selected-agency" : ""}" ${row.id === report.selectedId ? 'aria-current="true"' : ""}><td class="leadership-rank ranking-neutral">${row.totalRank ?? "—"}</td><td>${nameLink(row.id, row.name)}</td><td class="leadership-total ${row.totalChange === undefined ? '' : rankingTone(row.totalChange)}">${point(row.total, row.id, null)}</td><td class="ranking-change ${rankingTone(row.totalRankChange)}">${rankMovement(row.totalRankChange)}</td>${row.scores.map((score, i) => `<td class="${row.scoreChanges ? rankingTone(row.scoreChanges[i]) : ''}">${point(score, row.id, groups[i] ?? null)}</td><td class="leadership-group-rank">${row.ranks[i] ?? "—"}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
export function leadershipUpdatedLabel(report) {
    const format = (value) => new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", dateStyle: "short", timeStyle: "short" }).format(new Date(value));
    const first = report.capturedAt[0], last = report.capturedAt.at(-1);
    return first ? `${format(first)}${last && last !== first ? ` đến ${format(last)}` : ""} (giờ Việt Nam)` : "Chưa có thời điểm cập nhật";
}
export function buildLeadershipWorkbook(WorkbookClass, report) {
    const workbook = new WorkbookClass();
    workbook.creator = "Phân tích QĐ766";
    const sheet = workbook.addWorksheet("Bảng xếp hạng");
    sheet.properties.defaultRowHeight = 15;
    sheet.getCell("A1").value = "BẢNG XẾP HẠNG ĐÁNH GIÁ CHẤT LƯỢNG PHỤC VỤ";
    sheet.getCell("A2").value = `${report.period} · ${report.population} · ${report.scope}`;
    sheet.getCell("A3").value = `Cập nhật: ${leadershipUpdatedLabel(report)}`;
    sheet.getCell("A4").value = `Cơ quan đang chọn: ${report.selectedName}`;
    for (let row = 1; row <= 4; row++) {
        sheet.getRow(row).height = 15;
        sheet.getCell(row, 1).font = { name: "Calibri", size: 11, bold: row === 1 };
    }
    if (report.comparisonLabel)
        sheet.getCell('A5').value = report.comparisonLabel;
    const headers = ["Thứ hạng", report.nameHeader, "Tổng điểm", "Tăng/Giảm", ...report.groupLabels.flatMap(label => [label, "Hạng"])];
    const header = sheet.getRow(6);
    header.values = headers;
    header.height = 42;
    header.eachCell((cell, col) => {
        const color = col >= 5 ? leadershipColors[Math.floor((col - 5) / 2)] ?? "F1F5F9" : "F1F5F9";
        cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: `FF${color}` } };
        cell.font = { name: "Calibri", size: 10, bold: true };
        cell.alignment = { horizontal: "center", vertical: "middle", wrapText: true };
    });
    report.rows.forEach((item, index) => {
        const row = sheet.addRow([item.totalRank, item.name, item.total, item.totalRankChange ?? '—', ...item.scores.flatMap((score, i) => [score, item.ranks[i] ?? null])]);
        row.height = 15;
        row.eachCell({ includeEmpty: true }, (cell, col) => {
            const groupRank = col >= 6 && col % 2 === 0;
            const delta = col === 4 ? item.totalRankChange : col === 3 ? item.totalChange : col >= 5 && !groupRank ? item.scoreChanges?.[(col - 5) / 2] : undefined;
            const color = delta == null ? 'FF0F172A' : rankingTone(delta) === 'ranking-up' ? 'FF047857' : rankingTone(delta) === 'ranking-down' ? 'FFB91C1C' : 'FF475569';
            cell.font = { name: "Calibri", size: col === 4 ? 11 : 10, bold: col === 3 || col === 4 || groupRank, color: { argb: groupRank || col === 1 || col === 4 && delta == null ? 'FF475569' : color } };
            if (col === 4 && delta != null)
                cell.note = delta === 0 ? 'Thứ hạng không đổi' : `${delta > 0 ? '▲ Tăng' : '▼ Giảm'} ${Math.abs(delta)} bậc`;
            cell.alignment = { horizontal: col === 2 ? "left" : col === 1 || col === 4 || groupRank ? "center" : "right", vertical: "middle", wrapText: false };
            cell.numFmt = col === 4 ? '[>0]"▲ "0;[<0]"▼ "0;"—"' : col === 3 || col >= 5 && !groupRank ? "#,##0.00" : "#,##0";
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
        sheet.getColumn(column).width = column >= 5 ? Math.min(24, Math.ceil(width + 4)) : Math.min(255, Math.ceil(width + 4));
    });
    report.notes.forEach((note, index) => { const cell = sheet.getCell(end + 2 + index, 1); cell.value = note; cell.font = { name: "Calibri", size: 10, color: { argb: "FF64748B" } }; });
    sheet.autoFilter = { from: { row: 6, column: 1 }, to: { row: Math.max(6, end), column: headers.length } };
    sheet.views = [{ state: "frozen", xSplit: 2, ySplit: 6 }];
    sheet.pageSetup = { orientation: "landscape", paperSize: 9, fitToPage: true, fitToWidth: 1, fitToHeight: 0, printTitlesRow: "1:6", margins: { left: 0.25, right: 0.25, top: 0.3, bottom: 0.3, header: 0.1, footer: 0.1 } };
    return workbook;
}
//# sourceMappingURL=leadership-report.js.map