import { detailExportEntries } from './detail-export.js';
import { orderSatisfactionRows } from './satisfaction-display-order.js';
import { paymentDefinitions } from './payment-indicators.js';
import { changeTone } from './change-tone.js';
import { renderComboChart, bindComboCharts } from './daily-combo-chart.js';
import { renderDatePicker, bindDatePickers } from './daily-date-picker.js';
import { userFacingError } from './service-feedback.js';
/** Inclusive windows; availableDates is scoped to this unit, group and period.
 * Never substitute an older observation for a missing calendar day. */
export function dailyQuickRanges(body) {
    const end = body.current.reportDate, available = new Set(body.availableDates);
    if (!end || body.current.state !== 'available' || !available.has(end))
        return [];
    return [7, 30, 90].flatMap(days => {
        const cursor = new Date(end + 'T00:00:00Z');
        for (let i = 0; i < days; i++) {
            if (!available.has(cursor.toISOString().slice(0, 10)))
                return [];
            if (i < days - 1)
                cursor.setUTCDate(cursor.getUTCDate() - 1);
        }
        return [{ days, baseline: cursor.toISOString().slice(0, 10) }];
    });
}
const escape = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const numeric = (v) => typeof v === 'number' && Number.isFinite(v) ? v : null;
const round = (v) => Math.round((v + Number.EPSILON) * 100) / 100;
const number = (v, digits = 2) => v === null ? '—' : v.toLocaleString('vi-VN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
const dayLabel = (day) => day && /^\d{4}-\d{2}-\d{2}$/.test(day) ? day.split('-').reverse().join('/') : 'Chưa có ngày dữ liệu';
const difference = (before, after) => before == null || after == null ? null : after - before;
const signed = (v, digits = 2) => v === null ? '—' : `${round(v) > 0 ? '+' : ''}${number(round(v), digits)}`;
const deltaText = (v, digits = 2, suffix = '', unchanged = false) => v === null ? '—' : unchanged && round(v) === 0 ? 'Không đổi' : signed(v, digits) + suffix;
/** Online provincial details exist separately from an agency's group score. */
export function supportsDailyIndicators(group, entity, provinceId) {
    return group !== 'provide-online-tree' || entity !== null && (entity.departmentId === provinceId || entity.metrics.length > 0);
}
/** Same display projection as the current detail table; never rewrite source scores. */
export function indicatorValues(group, entity) {
    if (!entity)
        return [];
    return detailExportEntries(group, entity, 'all').map(entry => {
        if (entry.kind === 'parameter')
            return { key: entry.key, name: entry.name, numerator: numeric(entry.value), denominator: null, ratio: null, score: null, maximum: null, source: 'none', lowerBetter: false, reference: true, note: 'Số liệu tham khảo, không chấm điểm.' };
        const m = entry.metric;
        let ratio = numeric(m.ratio), note = '';
        const a = numeric(m.numerator), b = numeric(m.denominator);
        if (b === 0) {
            ratio = null;
            note = 'Tổng số bằng 0: không xác định tỷ lệ.';
        }
        if (a !== null && b !== null && (a < 0 || b < 0 || a > b)) {
            ratio = null;
            note = 'Số lượng đạt và tổng số chưa đủ điều kiện tính tỷ lệ.';
        }
        const maximum = numeric(m.apiMaxScore), rawScore = numeric(m.apiScore), reference = maximum !== null && maximum <= 0 || maximum === null && rawScore === null;
        const score = reference ? null : rawScore;
        // Progress uses its actual source group score; payment scores are display-only calculations.
        const source = score === null ? 'none' : entry.derived && group === 'formality-online-payment-tree' ? 'calculated' : 'source';
        if (source === 'calculated') {
            note += ' Điểm tính đối chiếu theo công thức hiển thị, không thay điểm nhóm do nguồn công bố.';
            const definition = paymentDefinitions.find(d => d.id === m.code);
            if (definition && definition.target < 100 && ratio !== null && ratio >= definition.target)
                note += ` Đạt ngưỡng ${definition.target}%, điểm chỉ tiêu đã tối đa.`;
        }
        if (source === 'source' && score !== null && maximum !== null && score >= maximum)
            note += ' Điểm nguồn đã đạt tối đa.';
        return { key: group === 'provide-online-tree' ? 'online:' + m.name : entry.key, name: m.name, numerator: a, denominator: b, ratio, score, maximum, source, reference,
            lowerBetter: group === 'dvc-progress-tree' && entry.key === 'totalOverdue' || group === 'provide-online-tree' && /quá hạn/.test(m.name), note: note.trim() };
    });
}
export function indicatorChanges(group, before, after) {
    const old = new Map(indicatorValues(group, before).map(v => [v.key, v])), fresh = indicatorValues(group, after);
    const current = new Map(fresh.map(v => [v.key, v]));
    const keys = [...current.keys(), ...[...old.keys()].filter(k => !current.has(k))];
    const rows = keys.map(key => {
        const a = old.get(key) ?? null, b = current.get(key) ?? null;
        let note = b?.note ?? a?.note ?? '';
        if (!a || !b)
            note += ' Chỉ tiêu chưa có đủ dữ liệu ở cả hai ngày.';
        if (a && b && a.maximum !== b.maximum)
            note += ' Điểm tối đa thay đổi giữa hai ngày; cần đối chiếu cách chấm điểm.';
        const sameScoreBasis = a?.source === b?.source;
        if (a && b && !sameScoreBasis)
            note += ' Cơ sở điểm khác nhau giữa hai ngày; không tính chênh điểm.';
        return { key, name: b?.name ?? a?.name ?? key, before: a, after: b, achieved: difference(a?.numerator, b?.numerator), total: difference(a?.denominator, b?.denominator),
            ratio: difference(a?.ratio, b?.ratio), score: sameScoreBasis ? difference(a?.score == null ? null : round(a.score), b?.score == null ? null : round(b.score)) : null, note: note.trim() };
    });
    return orderSatisfactionRows(group, rows);
}
function cell(before, after, delta, label, tone = 'change-neutral', digits = 2, suffix = '', unchanged = false) {
    if (before == null && after == null)
        return '<span class="daily-value-unavailable">—</span>';
    return `<div class="daily-value-pair"><span>${number(before ?? null, digits)}${before == null ? '' : suffix}</span><span aria-hidden="true">→</span><strong class="${tone}">${number(after ?? null, digits)}${after == null ? '' : suffix}</strong></div>${delta === null ? '' : `<small class="${tone}">${escape(deltaText(delta, digits, label, unchanged))}</small>`}`;
}
export function dailyComboModel(body, row) {
    const count = (value) => value != null && value >= 0 ? value : null;
    const daily = new Map((body.series ?? []).map(day => [day.reportDate, day]));
    daily.set(body.baseline.reportDate, body.baseline);
    daily.set(body.current.reportDate, body.current);
    const points = [];
    const start = body.baseline.reportDate, end = body.current.reportDate;
    if (start && end) {
        const cursor = new Date(start + 'T00:00:00Z');
        const priorDay = new Date(cursor);
        priorDay.setUTCDate(priorDay.getUTCDate() - 1);
        const prior = body.preceding?.reportDate === priorDay.toISOString().slice(0, 10) && body.preceding.state === 'available' ? indicatorValues(body.group, body.preceding.entity).find(v => v.key === row?.key) : null;
        let previous = count(prior?.numerator);
        // Reporting periods contain at most 366 calendar days. Never join across a gap.
        for (let i = 0; i < 366 && cursor.toISOString().slice(0, 10) <= end; i++, cursor.setUTCDate(cursor.getUTCDate() + 1)) {
            const day = cursor.toISOString().slice(0, 10), record = daily.get(day);
            const item = record?.state === 'available' ? indicatorValues(body.group, record.entity).find(v => v.key === row?.key) : null;
            const value = count(item?.numerator);
            points.push({ day, delta: difference(previous, value), ratio: item?.ratio ?? null, score: item?.score ?? null, maximum: item?.maximum ?? null });
            previous = value;
        }
    }
    return { points, mode: points.some(p => p.ratio !== null) || !points.some(p => p.score !== null) ? 'ratio' : 'score', name: row?.name ?? 'Chọn chỉ tiêu trong bảng' };
}
function countChart(body, row) {
    const model = dailyComboModel(body, row), delta = difference(row?.before?.numerator, row?.after?.numerator);
    const tone = changeTone(row?.before?.lowerBetter || row?.after?.lowerBetter ? delta === null ? null : -delta : delta);
    const ranges = dailyQuickRanges(body);
    const quick = ranges.length ? `<div class="daily-quick-ranges" role="group" aria-label="Chọn nhanh khoảng ngày">${ranges.map(range => `<button type="button" data-daily-indicator-range="${range.days}" aria-pressed="${body.baseline.reportDate === range.baseline}" title="${dayLabel(range.baseline)} – ${dayLabel(body.current.reportDate)}">${range.days} ngày</button>`).join('')}</div>` : '';
    return `<aside class="daily-indicator-chart" id="daily-indicator-chart" aria-label="Biểu đồ phát sinh và tỷ lệ theo ngày"><h3>Biến động theo ngày</h3>${quick}<p class="daily-chart-indicator">${escape(model.name)}</p>
 ${model.points.length ? renderComboChart(model) : '<div class="daily-chart-empty">—</div>'}
 ${delta === null ? '' : `<div class="daily-chart-change"><span>Biến động</span><strong class="${tone}">${deltaText(delta, 0, '', true)}</strong></div>`}</aside>`;
}
// Native name buttons retain keyboard activation; separate controls in a row
// must keep their own action instead of also selecting the indicator.
export function indicatorRowClick(event) {
    const target = event?.target;
    const control = target?.closest?.('button,a,input,select,textarea,label,summary,[role="button"],[contenteditable]:not([contenteditable="false"])');
    return !control || control.matches('button.row-link,button.daily-indicator-name');
}
export function renderIndicatorComparison(body, selected = null) {
    const rows = indicatorChanges(body.group, body.baseline.entity, body.current.entity);
    const selectedRow = rows.find(row => row.key === selected) ?? rows.find(row => row.before?.numerator != null && row.after?.numerator != null) ?? rows[0];
    const warnings = [body.current.state !== 'available' ? `Chưa có dữ liệu chi tiết ngày đánh giá ${dayLabel(body.current.reportDate)}.` : '',
        body.baseline.state !== 'available' ? body.baseline.state === 'outside-period' ? 'Ngày liền trước nằm ngoài kỳ báo cáo. Hãy chọn ngày làm mốc trong cùng kỳ.' : `Chưa có dữ liệu chi tiết ngày làm mốc ${dayLabel(body.baseline.reportDate)}. Không dùng ngày khác thay thế.` : ''].filter(Boolean);
    const select = (role, selected) => renderDatePicker(role, selected, body.availableDates, role === 'baseline' ? body.current.reportDate : body.baseline.reportDate);
    const groupDelta = difference(body.baseline.entity?.apiScore, body.current.entity?.apiScore);
    const content = `<div class="daily-indicator-toolbar">${select('baseline', body.baseline.reportDate)}${select('current', body.current.reportDate)}<div class="daily-group-change"><span>Điểm nhóm · theo nguồn</span><strong class="${changeTone(groupDelta)}">${deltaText(groupDelta, 2, ' điểm', true)}</strong>${body.baseline.entity?.apiScore != null || body.current.entity?.apiScore != null ? `<small>${number(body.baseline.entity?.apiScore ?? null)} → ${number(body.current.entity?.apiScore ?? null)}</small>` : ''}</div></div>
 <p class="daily-indicator-context">${dayLabel(body.current.reportDate)} so với ${dayLabel(body.baseline.reportDate)} · Dữ liệu lũy kế trong cùng kỳ báo cáo.</p>
 ${warnings.map(w => `<p class="daily-indicator-warning" role="status">${escape(w)}</p>`).join('')}
 ${rows.length ? `<table class="daily-indicator-table"><thead><tr><th>Chỉ tiêu / số liệu nghiệp vụ</th><th>Số lượng đạt</th><th>Tổng số</th><th>Tỷ lệ</th><th>Điểm</th></tr></thead><tbody>${rows.map(row => {
        const metric = row.after ?? row.before;
        const ratioTone = changeTone(metric?.lowerBetter && row.ratio !== null ? -row.ratio : row.ratio);
        return `<tr class="daily-selectable-row${selectedRow?.key === row.key ? ' daily-selected' : ''}" data-daily-indicator-row="${escape(row.key)}"><td><button type="button" class="daily-indicator-name" aria-pressed="${selectedRow?.key === row.key}" aria-controls="daily-indicator-chart">${escape(row.name)}</button></td>
  <td class="daily-count" data-label="Số lượng đạt">${cell(row.before?.numerator, row.after?.numerator, row.achieved, '', 'change-neutral', 0)}</td>
  <td class="daily-count" data-label="Tổng số">${cell(row.before?.denominator, row.after?.denominator, row.total, '', 'change-neutral', 0)}</td>
  <td data-label="Tỷ lệ">${cell(row.before?.ratio, row.after?.ratio, row.ratio, ' điểm %', ratioTone, 2, '%', true)}</td>
  <td data-label="Điểm"${metric?.source === 'calculated' ? ' title="Điểm tính đối chiếu theo công thức hiển thị; không thay điểm nhóm nguồn công bố."' : ''}>${cell(row.before?.score, row.after?.score, row.score, ' điểm', changeTone(row.score), 2, '', true)}</td></tr>`;
    }).join('')}</tbody></table>` : '<p class="daily-indicator-empty">Chưa có chỉ tiêu chi tiết để so sánh ở hai ngày được chọn.</p>'}`;
    return `<div class="daily-indicator-columns"><div class="daily-indicator-metrics">${content}</div>${countChart(body, selectedRow)}</div>`;
}
export class DailyIndicatorPanel {
    changed;
    read;
    entries = new Map();
    activeKey = '';
    revision = 0;
    controller = null;
    cleanWidgets = () => { };
    // Native Window.fetch must not be invoked as a method of this panel instance.
    constructor(changed, read = (input, init) => globalThis.fetch(input, init)) {
        this.changed = changed;
        this.read = read;
    }
    key(c) { return [c.accountId, c.provinceId, c.unitId, c.period.id, c.group].join(':'); }
    open(c) { const e = this.entries.get(this.key(c)); if (e && !e.loading && Date.now() - e.loadedAt > 300000) {
        e.body = null;
        e.html = null;
        e.error = '';
    } }
    pause() { this.cleanWidgets(); const entry = this.entries.get(this.activeKey); if (entry?.loading) {
        entry.loading = false;
        entry.request = ++this.revision;
    } this.activeKey = ''; this.controller?.abort(); this.controller = null; }
    render(c) {
        const key = this.key(c);
        this.activeKey = key;
        let entry = this.entries.get(key);
        if (!entry) {
            entry = { loading: false, error: '', body: null, selected: null, html: null, request: 0, loadedAt: 0 };
            this.entries.set(key, entry);
            if (this.entries.size > 36) {
                const first = this.entries.keys().next().value;
                if (first && first !== key)
                    this.entries.delete(first);
            }
            void this.load(c, entry);
        }
        else if (!entry.body && !entry.loading && !entry.error)
            void this.load(c, entry);
        if (entry.loading)
            return '<div class="daily-indicator-loading" role="status">Đang đọc hai bản dữ liệu đã lưu…</div>';
        if (entry.error)
            return `<div class="daily-indicator-empty"><p role="alert">${escape(entry.error)}</p><button type="button" class="btn" data-daily-indicator-retry>Thử lại</button></div>`;
        const body = entry.body;
        if (!body?.availableDates.length)
            return '<div class="daily-indicator-empty">Chưa có lịch sử dữ liệu chi tiết theo ngày của cơ quan và nhóm chỉ tiêu này.</div>';
        return entry.html ?? (entry.html = renderIndicatorComparison(body, entry.selected));
    }
    async load(c, entry, current = '', baseline = '') {
        this.controller?.abort();
        const controller = new AbortController();
        this.controller = controller;
        const key = this.key(c), revision = ++this.revision;
        entry.request = revision;
        entry.loading = true;
        entry.error = '';
        const query = new URLSearchParams({ root_department_id: c.provinceId, unit_id: c.unitId, group: c.group, period_type: c.period.type, year: String(c.period.year), scope: 'all' });
        if (c.period.value != null)
            query.set('period_value', String(c.period.value));
        if (current)
            query.set('current_date', current);
        if (baseline)
            query.set('baseline_date', baseline);
        try {
            const response = await this.read('/api/v1/dashboard/daily-indicator-comparison?' + query, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]), cache: 'no-store' });
            const body = await response.json();
            if (!response.ok)
                throw new Error(typeof body.detail === 'string' ? body.detail : 'Chưa đọc được dữ liệu biến động theo ngày.');
            const validDay = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && Number.isFinite(Date.parse(v)) && new Date(v + 'T00:00:00Z').toISOString().slice(0, 10) === v;
            const validRecord = (v) => v && ['available', 'missing', 'outside-period'].includes(v.state) && (v.reportDate === null || validDay(v.reportDate)) &&
                (v.entity === null || v.entity.departmentId === c.unitId && Array.isArray(v.entity.metrics) && typeof v.entity.parameters === 'object' && v.entity.parameters !== null);
            const inPeriod = (v) => Number(v.slice(0, 4)) === c.period.year && (c.period.type === 'year' || c.period.type === 'month' && Number(v.slice(5, 7)) === c.period.value || c.period.type === 'quarter' && Math.ceil(Number(v.slice(5, 7)) / 3) === c.period.value);
            if (body.scope !== 'all' || body.unitId !== c.unitId || body.group !== c.group || !Array.isArray(body.availableDates) || !body.availableDates.every((v) => validDay(v) && inPeriod(v)) || !validRecord(body.current) || !validRecord(body.baseline))
                throw new Error('Dữ liệu trả về không đúng cơ quan hoặc nhóm chỉ tiêu.');
            if (body.series !== undefined && (!Array.isArray(body.series) || body.series.length > 366 || !body.series.every((v) => validRecord(v) && v.reportDate !== null && v.reportDate >= body.baseline.reportDate && v.reportDate <= body.current.reportDate && (v.state === 'outside-period' || inPeriod(v.reportDate))) || new Set(body.series.map((v) => v.reportDate)).size !== body.series.length))
                throw new Error('Dữ liệu theo ngày trả về không đúng kỳ báo cáo hoặc cơ quan.');
            if (body.preceding != null) {
                const previous = new Date(body.baseline.reportDate + 'T00:00:00Z');
                previous.setUTCDate(previous.getUTCDate() - 1);
                if (!validRecord(body.preceding) || body.preceding.reportDate !== previous.toISOString().slice(0, 10) || body.preceding.state === 'available' && !inPeriod(body.preceding.reportDate))
                    throw new Error('Dữ liệu ngày trước mốc không đúng kỳ báo cáo hoặc cơ quan.');
            }
            if (entry.request === revision && !controller.signal.aborted) {
                entry.body = body;
                entry.html = null;
                entry.loadedAt = Date.now();
            }
        }
        catch (e) {
            if (entry.request === revision && !controller.signal.aborted)
                entry.error = userFacingError(e, 'Chưa thể tải dữ liệu đã lưu. Vui lòng thử lại.');
        }
        finally {
            if (entry.request === revision)
                entry.loading = false;
            if (this.controller === controller)
                this.controller = null;
            if (this.activeKey === key && !controller.signal.aborted)
                this.changed();
        }
    }
    bind(c, doc = document) {
        this.cleanWidgets();
        this.cleanWidgets = () => { };
        const key = this.key(c), entry = this.entries.get(key);
        if (!entry || this.activeKey !== key)
            return;
        doc.querySelector('[data-daily-indicator-retry]')?.addEventListener('click', () => { void this.load(c, entry); this.changed(); });
        doc.querySelectorAll('[data-daily-indicator-range]').forEach(el => el.addEventListener('click', () => {
            const body = entry.body;
            if (this.activeKey !== key || entry.loading || !body)
                return;
            const range = dailyQuickRanges(body).find(r => r.days === Number(el.dataset.dailyIndicatorRange));
            if (!range || range.baseline === body.baseline.reportDate)
                return;
            void this.load(c, entry, body.current.reportDate ?? '', range.baseline);
            this.changed();
        }));
        doc.querySelectorAll('[data-daily-indicator-row]').forEach(el => el.addEventListener('click', event => { if (this.activeKey !== key || !indicatorRowClick(event))
            return; const selected = el.dataset.dailyIndicatorRow ?? null; if (entry.selected === selected)
            return; entry.selected = selected; entry.html = null; this.changed(); }));
        doc.querySelectorAll('[data-daily-indicator-date]').forEach(el => el.addEventListener('change', () => {
            const body = entry.body;
            if (this.activeKey !== key || !body || !body.availableDates.includes(el.value))
                return;
            let current = body.current.reportDate ?? '', baseline = body.baseline.reportDate ?? '';
            if (el.dataset.dailyIndicatorDate === 'current') {
                if (baseline && el.value <= baseline)
                    return;
                current = el.value;
            }
            else {
                if (el.value >= current)
                    return;
                baseline = el.value;
            }
            void this.load(c, entry, current, baseline);
            this.changed();
        }));
        const calendarCleanup = bindDatePickers(doc), chartCleanup = bindComboCharts(doc);
        this.cleanWidgets = () => { calendarCleanup(); chartCleanup(); };
    }
}
//# sourceMappingURL=daily-indicator-comparison.js.map