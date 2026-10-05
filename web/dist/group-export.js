import { parameterLabels } from './parameter-labels.js';
import { analysisExcelFilename } from './excel-export.js';
const sheetNames = { transparency: 'Công khai minh bạch', 'dvc-progress-tree': 'Tiến độ giải quyết', 'provide-online-tree': 'Dịch vụ công trực tuyến', 'dossier-digitized': 'Số hóa hồ sơ', 'handling-satisfaction': 'Mức độ hài lòng', 'formality-online-payment-tree': 'Thanh toán trực tuyến' };
const metricKey = (metric) => JSON.stringify([metric.code, metric.name]);
const stamp = (value) => value ? new Date(value).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : 'Chưa có';
const level = (value) => value === 'COMMUNE' ? 'Xã, phường' : value === 'PROVINCE' ? 'Cấp tỉnh' : value ?? '';
export function buildGroupWorkbook(WorkbookClass, data, context) {
    const workbook = new WorkbookClass();
    workbook.creator = 'Phân tích QĐ766';
    for (const group of data.groups) {
        const sheet = workbook.addWorksheet(sheetNames[group.id]);
        const metrics = new Map();
        const parameters = new Set();
        for (const entity of group.entities) {
            for (const metric of entity.metrics ?? [])
                if (metric.code !== 'scoreDelta')
                    metrics.set(metricKey(metric), metric);
            for (const key of Object.keys(entity.parameters ?? {}))
                if (key !== 'scoreDelta' && parameterLabels[key])
                    parameters.add(key);
        }
        const metricList = Array.from(metrics.values());
        const parameterList = Array.from(parameters).sort();
        const labels = ['STT', 'Cơ quan, đơn vị', 'Cấp cơ quan', 'Điểm ghi nhận', 'Điểm tối đa', 'Tỷ lệ đạt'];
        const top = [...labels];
        const bottom = [...labels];
        for (const metric of metricList) {
            top.push(metric.name, '', '', '', '');
            bottom.push('Số lượng đạt', 'Tổng số', 'Tỷ lệ', 'Điểm ghi nhận', 'Điểm tối đa');
        }
        for (const key of parameterList) {
            top.push(parameterLabels[key]);
            bottom.push(parameterLabels[key]);
        }
        top.push('Trạng thái dữ liệu');
        bottom.push('Trạng thái dữ liệu');
        sheet.addRow([group.label.toLocaleUpperCase('vi-VN')]);
        sheet.addRow([context.name, context.period, context.scope]);
        sheet.addRow([`Điểm tỉnh: ${stamp(data.delivery?.capturedAt)} · Chi tiết nhóm: ${stamp(group.capturedAt)} (giờ Việt Nam)`]);
        sheet.addRow([`Phạm vi: ${data.accessScope === 'agency' ? 'Cơ quan được phân quyền' : 'Các cơ quan trong tỉnh'}${data.delivery?.stale ? ' · Dữ liệu quá hạn cập nhật' : ''}${data.delivery?.provisional ? ' · Kỳ chưa kết thúc' : ''}`]);
        sheet.addRow(top);
        sheet.addRow(bottom);
        // Merge only presentation labels, never metadata or data cells.
        for (let c = 1; c <= 6; c++)
            sheet.mergeCells(5, c, 6, c);
        for (let i = 0; i < metricList.length; i++)
            sheet.mergeCells(5, 7 + i * 5, 5, 11 + i * 5);
        for (let c = 7 + metricList.length * 5; c <= bottom.length; c++)
            sheet.mergeCells(5, c, 6, c);
        const entities = new Map(group.entities.map(entity => [entity.departmentId, entity]));
        data.units.forEach((unit, index) => {
            const entity = entities.get(unit.departmentId);
            const row = [index + 1, unit.departmentName, level(unit.departmentLevel), entity?.apiScore ?? null, entity?.apiMaxScore ?? null, entity?.apiRatio == null ? null : entity.apiRatio / 100];
            const actual = new Map((entity?.metrics ?? []).map(metric => [metricKey(metric), metric]));
            for (const descriptor of metricList) {
                const metric = actual.get(metricKey(descriptor));
                row.push(metric?.numerator ?? null, metric?.denominator ?? null, metric?.ratio == null ? null : metric.ratio / 100, metric?.apiScore ?? null, metric?.apiMaxScore ?? null);
            }
            for (const key of parameterList) {
                const value = entity?.parameters?.[key];
                row.push(typeof value === 'number' || typeof value === 'string' || typeof value === 'boolean' ? value : null);
            }
            const detail = Boolean(entity?.metrics?.length || Object.keys(entity?.parameters ?? {}).some(key => Boolean(parameterLabels[key])));
            row.push(!entity ? 'Chưa có dữ liệu nhóm' : entity.apiScore == null ? 'Chưa có điểm nhóm' : !detail ? 'Nguồn chưa cung cấp số liệu thành phần' : 'Có dữ liệu');
            sheet.addRow(row);
        });
        const last = sheet.rowCount;
        sheet.eachRow((row, index) => {
            row.height = index === 5 ? 30 : 15;
            row.eachCell({ includeEmpty: true }, (cell, column) => {
                cell.font = { name: 'Calibri', size: 11, color: { argb: 'FF172554' } };
                cell.alignment = { vertical: 'middle', horizontal: typeof cell.value === 'number' ? 'right' : 'left' };
                if (index === 5 || index === 6) {
                    cell.font = { name: 'Calibri', size: 11, bold: true, color: { argb: 'FFFFFFFF' } };
                    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF4338CA' } };
                    cell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: index === 5 };
                }
                else if (index > 6 && index % 2 === 0)
                    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF4F7FE' } };
                if (index > 6 && typeof cell.value === 'number') {
                    const offset = column - 7;
                    const metricPart = offset >= 0 && offset < metricList.length * 5 ? offset % 5 : null;
                    const parameter = parameterList[column - (7 + metricList.length * 5)];
                    const decimalParameter = parameter === 'averageScore' || parameter === 'avgProcessingDays';
                    cell.numFmt = column === 6 || metricPart === 2 ? '0.00%' : column === 1 || metricPart === 0 || metricPart === 1 ? '#,##0' : column >= 7 + metricList.length * 5 && !decimalParameter && Number.isInteger(cell.value) ? '#,##0' : '#,##0.00';
                }
            });
        });
        sheet.getCell('A1').font = { name: 'Calibri', size: 14, bold: true, color: { argb: 'FF172554' } };
        for (let column = 1; column <= bottom.length; column++) {
            let width = Math.max(12, (bottom[column - 1]?.length ?? 0) + 3);
            for (let row = 7; row <= last; row++) {
                const value = sheet.getCell(row, column).value;
                const displayed = typeof value === 'number' ? value.toLocaleString('vi-VN', { maximumFractionDigits: 2 }) : sheet.getCell(row, column).text;
                width = Math.max(width, displayed.length + 3);
            }
            sheet.getColumn(column).width = width;
        }
        sheet.views = [{ state: 'frozen', xSplit: 3, ySplit: 6, showGridLines: false }];
        sheet.autoFilter = { from: { row: 6, column: 1 }, to: { row: last, column: bottom.length } };
        sheet.pageSetup = { orientation: 'landscape', paperSize: 9, fitToPage: true, fitToWidth: 1, fitToHeight: 0, printTitlesRow: '5:6', printTitlesColumn: 'A:C' };
    }
    return workbook;
}
export function openGroupExport(options) {
    const dialog = document.createElement('dialog');
    dialog.className = 'group-export-dialog';
    dialog.setAttribute('aria-label', 'Tải biểu Excel');
    // Context comes from the currently viewed selection; write user text via textContent.
    dialog.innerHTML = '<form method="dialog"><div class="modal-top"><strong>Tải biểu Excel</strong><button class="btn small" aria-label="Đóng">Đóng</button></div></form><p data-context></p><p class="muted" data-scope></p><label>Nhóm chỉ tiêu <select class="btn" data-groups></select></label><p role="status" data-status></p><button type="button" class="btn primary" data-download>Tải Excel</button>';
    dialog.querySelector('[data-context]').textContent = `${options.context.name} · ${options.context.period}`;
    dialog.querySelector('[data-scope]').textContent = options.agency ? 'Chỉ xuất cơ quan được phân quyền.' : 'Xuất các cơ quan, đơn vị trong tỉnh đang xem.';
    const selection = dialog.querySelector('[data-groups]');
    for (const [id, label] of [['all', 'Cả 6 nhóm chỉ tiêu'], ...Object.entries(sheetNames)]) {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = label;
        selection.append(option);
    }
    selection.value = options.defaultAll ? 'all' : options.group;
    const button = dialog.querySelector('[data-download]');
    button.addEventListener('click', async () => {
        button.disabled = true;
        const status = dialog.querySelector('[data-status]');
        status.textContent = 'Đang tạo biểu Excel…';
        try {
            const query = new URLSearchParams(options.query);
            query.set('group', selection.value);
            const response = await fetch(`/api/v1/dashboard/group-export?${query}`, { credentials: 'same-origin' });
            const body = await response.json();
            if (!response.ok)
                throw new Error(typeof body.detail === 'string' ? body.detail : 'Không thể xuất biểu Excel. Vui lòng thử lại.');
            const data = body;
            const workbook = buildGroupWorkbook(options.WorkbookClass, data, options.context);
            const url = URL.createObjectURL(new Blob([await workbook.xlsx.writeBuffer()], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }));
            const link = document.createElement('a');
            link.href = url;
            const snapshot = { ...options.context.snapshot, ...(data.delivery ? { delivery: data.delivery } : {}) };
            link.download = analysisExcelFilename(options.context.name, snapshot, 'details');
            document.body.append(link);
            link.click();
            link.remove();
            window.setTimeout(() => URL.revokeObjectURL(url), 1000);
            status.textContent = 'Đã tải biểu Excel.';
            dialog.close();
        }
        catch (error) {
            status.textContent = error instanceof Error ? error.message : 'Không thể xuất biểu Excel.';
        }
        finally {
            button.disabled = false;
        }
    });
    dialog.addEventListener('close', () => dialog.remove());
    document.body.append(dialog);
    dialog.showModal();
}
//# sourceMappingURL=group-export.js.map