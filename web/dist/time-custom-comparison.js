import { changeTone } from './change-tone.js';
export const comparisonEscape = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const n = (v) => v == null ? '—' : v.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export function customComparisonTable(current, baseline, groups, labels) {
    const newerIndex = Number.isFinite(current.chronology) && Number.isFinite(baseline.chronology) && (baseline.chronology ?? 0) > (current.chronology ?? 0) ? 1 : 0;
    const rows = [current, baseline], newer = rows[newerIndex], older = rows[1 - newerIndex];
    const difference = (a, b) => a != null && b != null ? a - b : null;
    const delta = difference(newer.total, older.total);
    return `<div class="table-wrap"><table><thead><tr><th>Kỳ</th><th>Tổng điểm</th><th>Điểm kỳ trước</th><th>Tăng/giảm điểm</th><th>Thứ hạng</th>${groups.map(g => `<th>${comparisonEscape(labels[g])}</th>`).join('')}</tr></thead><tbody>${rows.map((row, i) => {
        const isNewer = i === newerIndex;
        return `<tr><td>${comparisonEscape(row.label)} <span class="badge">${i ? 'Mốc' : 'So sánh'}</span>${row.provisional ? ' <span class="badge warn">Tạm thời</span>' : ''}</td><td class="num ${isNewer ? changeTone(delta) : ''}">${n(row.total)}</td><td class="num">${isNewer ? n(older.total) : '—'}</td><td class="num ${isNewer ? changeTone(delta) : ''}">${!isNewer || delta == null ? '—' : (delta >= 0 ? '+' : '') + n(delta)}</td><td class="num">${comparisonEscape(row.rank)}</td>${groups.map(g => `<td class="num ${isNewer ? changeTone(difference(row.groups[g], older.groups[g])) : ''}">${n(row.groups[g])}</td>`).join('')}</tr>`;
    }).join('')}</tbody></table></div>`;
}
//# sourceMappingURL=time-custom-comparison.js.map