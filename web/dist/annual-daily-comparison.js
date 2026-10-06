import { dailyChanges } from './daily-history.js';
import { changeTone } from './change-tone.js';
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = (v) => v.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const FIRST_DAILY_DATE = '2026-10-06';
/** Only the annual overview hero uses daily observations. Gauge stays latest. */
export function annualDailyComparison(history, selectedDate, loading = false, error = '') {
    const days = [...(history?.days ?? [])].filter(day => day.reportDate >= FIRST_DAILY_DATE).sort((a, b) => b.reportDate.localeCompare(a.reportDate));
    const selected = days.find(day => day.reportDate === selectedDate) ?? days[0];
    const change = dailyChanges(selected ? days.filter(day => day.reportDate <= selected.reportDate) : []);
    const calendar = `<input type="date" data-annual-observation aria-label="Ngày quan sát điểm năm" min="${FIRST_DAILY_DATE}" max="${esc(days[0]?.reportDate ?? FIRST_DAILY_DATE)}" value="${esc(selected?.reportDate ?? '')}" ${!days.length ? 'disabled' : ''}>`;
    const status = loading ? 'Đang tải…' : error ? 'Chưa đọc được dữ liệu' : !selected ? 'Chưa có lịch sử ngày' : change.points === null ? 'Chưa có ngày liền trước' : `${change.points > 0 ? '+' : ''}${num(change.points)} điểm`;
    return `<div class="annual-daily-comparison"><span>So với ngày trước</span><label class="annual-date-control"><span class="sr-only">Ngày quan sát điểm năm</span>${calendar}</label><strong class="${changeTone(change.points)}">${esc(status)}</strong><small>${selected ? `Điểm ngày chọn: ${selected.totalScore == null ? '—' : num(selected.totalScore)} · Tham khảo` : 'Biến động điểm năm · Tham khảo'}</small>${error ? '<button class="annual-retry" data-daily-refresh>Thử lại</button>' : ''}</div>`;
}
//# sourceMappingURL=annual-daily-comparison.js.map