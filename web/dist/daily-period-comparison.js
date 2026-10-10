import { dailyCalendar, FIRST_DAILY_DATE, formatDay, precedingDate } from './annual-daily-comparison.js';
import { changeTone } from './change-tone.js';
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const number = (v) => v == null ? '—' : v.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export function historyWithinPeriod(history, period) {
    const firstMonth = period.type === 'year' ? 1 : period.type === 'quarter' ? ((period.value ?? 1) - 1) * 3 + 1 : (period.value ?? 1);
    const monthCount = period.type === 'year' ? 12 : period.type === 'quarter' ? 3 : 1;
    const start = `${period.year}-${String(firstMonth).padStart(2, '0')}-01`;
    const end = new Date(Date.UTC(period.year, firstMonth - 1 + monthCount, 1)).toISOString().slice(0, 10);
    return { ...history, days: history.days.filter(day => day.reportDate >= start && day.reportDate < end) };
}
export function compareDailyDates(history, dates) {
    const days = [...(history?.days ?? [])].filter(d => d.reportDate >= FIRST_DAILY_DATE).sort((a, b) => b.reportDate.localeCompare(a.reportDate));
    const currentDate = dates?.current ?? days[0]?.reportDate ?? '';
    const baselineDate = dates?.baseline ?? (currentDate ? precedingDate(currentDate) : '');
    const current = days.find(d => d.reportDate === currentDate), baseline = days.find(d => d.reportDate === baselineDate);
    return { days, currentDate, baselineDate, current, baseline };
}
export function renderDailyDateComparison(history, groups, labels, dates, loading = false, error = '') {
    const { days, currentDate, baselineDate, current, baseline } = compareDailyDates(history, dates);
    const earliestDate = days.at(-1)?.reportDate ?? FIRST_DAILY_DATE;
    const delta = (a, b) => a != null && b != null ? a - b : null;
    const rows = [{ label: 'Tổng điểm', a: current?.totalScore, b: baseline?.totalScore }, ...groups.map(id => ({ label: labels[id], a: current?.groups[id]?.score, b: baseline?.groups[id]?.score }))];
    const status = loading ? 'Đang tải lịch sử ngày…' : error || (!days.length ? 'Chưa có lịch sử theo ngày trong kỳ này.' : !current || !baseline ? 'Ngày được chọn chưa có dữ liệu. Không tự thay mốc so sánh.' : '');
    return `<section class="panel daily-date-comparison"><div class="panel-head"><div><h2>So sánh hai ngày trong kỳ</h2><p>Cùng cơ quan, kỳ báo cáo và phạm vi. Tăng/giảm = Ngày dữ liệu − Ngày đối chiếu.</p></div></div><div class="daily-date-toolbar"><div><strong>Ngày dữ liệu</strong>${dailyCalendar('data-time-day="current"', 'Ngày dữ liệu', currentDate, earliestDate, days[0]?.reportDate ?? FIRST_DAILY_DATE, !days.length)}</div><div><strong>Ngày đối chiếu</strong>${dailyCalendar('data-time-day="baseline"', 'Ngày đối chiếu', baselineDate, earliestDate, days[0]?.reportDate ?? FIRST_DAILY_DATE, !days.length)}</div></div>${status ? `<p class="collection-feedback" role="status">${esc(status)}</p>` : ''}<div class="table-wrap"><table><thead><tr><th>Chỉ tiêu</th><th>Ngày dữ liệu${currentDate ? ` · ${esc(formatDay(currentDate))}` : ''}</th><th>Ngày đối chiếu${baselineDate ? ` · ${esc(formatDay(baselineDate))}` : ''}</th><th>Tăng/giảm điểm</th></tr></thead><tbody>${rows.map(row => { const change = delta(row.a, row.b); return `<tr><td>${esc(row.label)}</td><td class="num">${number(row.a)}</td><td class="num">${number(row.b)}</td><td class="num ${changeTone(change)}">${change == null ? '—' : `${change >= 0 ? '+' : ''}${number(change)}`}</td></tr>`; }).join('')}</tbody></table></div></section>`;
}
//# sourceMappingURL=daily-period-comparison.js.map