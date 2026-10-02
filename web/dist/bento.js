const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const number = (v) => v === null ? '—' : v.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const groupColors = { transparency: '#2563eb', 'dvc-progress-tree': '#059669', 'provide-online-tree': '#db2777', 'dossier-digitized': '#7c3aed', 'handling-satisfaction': '#d97706', 'formality-online-payment-tree': '#0891b2' };
const paths = {
    shield: '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z"/><path d="m8 12 3 3 5-6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    monitor: '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/>',
    document: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Z"/><path d="M14 3v6h6M8 13h8m-8 4h5"/>',
    star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>',
    card: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M3 10h18m-13 5h3"/>',
    warning: '<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3h.01"/>',
    chart: '<path d="M4 20V10m6 10V4m6 16v-7m5 7H2"/>',
};
const icons = { transparency: 'shield', 'dvc-progress-tree': 'clock', 'provide-online-tree': 'monitor', 'dossier-digitized': 'document', 'handling-satisfaction': 'star', 'formality-online-payment-tree': 'card' };
export function icon(name) { return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] ?? paths.chart}</svg>`; }
export function groupIcon(id) { return icon(icons[id]); }
export function gauge(score, maximum) {
    const ratio = score !== null && maximum ? Math.max(0, Math.min(1, score / maximum)) : 0;
    return `<div class="hero-gauge"><svg viewBox="0 0 300 250" role="img" aria-label="${score === null ? 'Chưa có tổng điểm' : `Tổng điểm ${number(score)} trên ${number(maximum)}`}" class="radial-gauge"><defs><linearGradient id="hero-spectrum" x1="0" y1="1" x2="1" y2="0"><stop stop-color="#34d399"/><stop offset=".32" stop-color="#22d3ee"/><stop offset=".68" stop-color="#4f46e5"/><stop offset="1" stop-color="#c026d3"/></linearGradient></defs><path d="M65 213a112 112 0 1 1 170 0" fill="none" stroke="#edf0fc" stroke-width="19" stroke-linecap="round"/><path d="M65 213a112 112 0 1 1 170 0" fill="none" stroke="url(#hero-spectrum)" stroke-width="19" stroke-linecap="round" pathLength="100" stroke-dasharray="${ratio * 100} 100"${ratio === 0 ? ' opacity="0"' : ''}/></svg><div class="gauge-number"><strong>${number(score)}</strong><span>trên ${number(maximum)} điểm</span></div></div>`;
}
export function trendChart(points, groupIds) {
    const series = [{ name: 'Tổng điểm', color: '#2563eb', values: points.map(p => p.view.totalScore) }, ...groupIds.map(id => ({ name: points.at(-1)?.view.groups.find(g => g.id === id)?.label ?? id, color: groupColors[id], values: points.map(p => { const g = p.view.groups.find(g => g.id === id); return g && g.score.value !== null && g.maximum ? g.score.value / g.maximum * 100 : null; }) }))];
    if (points.filter(p => p.view.totalScore !== null).length < 2)
        return '<div class="bento-empty">' + icon('chart') + '<strong>Chưa đủ lịch sử cùng loại kỳ</strong><span>Cần ít nhất hai kỳ có dữ liệu của cơ quan đang chọn.</span></div>';
    const x = (i) => 50 + i * 590 / Math.max(1, points.length - 1), y = (v) => 210 - Math.max(0, Math.min(100, v)) * 1.8;
    let svg = '<svg class="trend-svg" viewBox="0 0 670 255" role="img" aria-label="Xu hướng điểm theo các kỳ cùng loại. Tổng điểm trên 100; nhóm chỉ tiêu quy đổi phần trăm điểm tối đa.">';
    for (const v of [0, 25, 50, 75, 100])
        svg += `<line x1="50" x2="640" y1="${y(v)}" y2="${y(v)}" stroke="#edf0f8"/><text x="35" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
    series.forEach((s, k) => {
        const segments = [];
        let segment = [];
        s.values.forEach((v, i) => { if (v === null || (i > 0 && points[i].order - points[i - 1].order !== 1)) {
            if (segment.length)
                segments.push(segment);
            segment = [];
        } if (v !== null)
            segment.push([x(i), y(v)]); });
        if (segment.length)
            segments.push(segment);
        svg += `<defs><linearGradient id="trend-fill-${k}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="${s.color}" stop-opacity=".15"/><stop offset="1" stop-color="${s.color}" stop-opacity="0"/></linearGradient></defs>`;
        segments.forEach(seg => { const d = seg.map((p, i) => `${i ? 'L' : 'M'}${p[0]},${p[1]}`).join(' '); if (k === 0 && seg.length > 1)
            svg += `<path d="${d} L${seg.at(-1)[0]},210 L${seg[0][0]},210 Z" fill="url(#trend-fill-${k})"/>`; svg += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linejoin="round"/>`; });
        s.values.forEach((v, i) => { if (v !== null)
            svg += `<circle cx="${x(i)}" cy="${y(v)}" r="3.5" fill="${s.color}" stroke="white" stroke-width="1.5"><title>${esc(points[i].label)} · ${esc(s.name)}: ${number(v)}${k ? '%' : ' điểm'}</title></circle>`; });
    });
    points.forEach((p, i) => { if (points.length <= 6 || i % Math.ceil(points.length / 6) === 0 || i === points.length - 1)
        svg += `<text x="${x(i)}" y="238" text-anchor="middle">${esc(p.label.replace(/\/\d{4}/, ''))}</text>`; });
    return `<div class="chart-legend">${series.map(s => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join('')}</div>${svg}</svg><p class="bento-footnote">Tổng điểm: thang 100. Hai nhóm: % điểm tối đa, không phải tỷ lệ hồ sơ. Kỳ thiếu dữ liệu không nối đường.</p>`;
}
export function composition(view) {
    const complete = view.groups.length === 6 && view.groups.every(g => g.score.value !== null);
    const sum = view.groups.reduce((s, g) => s + (g.score.value ?? 0), 0);
    if (!complete)
        return '<div class="bento-empty">' + icon('chart') + '<strong>Chưa đủ điểm sáu nhóm</strong><span>Không tính cơ cấu từ dữ liệu thiếu.</span></div>';
    return `<div class="composition-stack" aria-label="Tỷ trọng điểm sáu nhóm">${view.groups.map(g => `<i style="width:${sum ? (g.score.value ?? 0) / sum * 100 : 0}%;background:${groupColors[g.id]}" title="${esc(g.label)}: ${number(g.score.value)} điểm"></i>`).join('')}</div><div class="composition-list">${view.groups.map(g => `<div><span class="composition-label"><i style="background:${groupColors[g.id]}"></i>${esc(g.label)}</span><strong>${number(g.score.value)} <small>đ</small></strong><span>${sum ? ((g.score.value ?? 0) / sum * 100).toLocaleString('vi-VN', { maximumFractionDigits: 1 }) + '%' : '—'}</span></div>`).join('')}</div><p class="bento-footnote">Tỷ trọng trên tổng điểm sáu nhóm${sum === 0 ? ' (tổng bằng 0)' : ''}. Tổng điểm chính giữ nguyên giá trị nguồn; có thể lệch nhẹ do làm tròn.</p>`;
}
//# sourceMappingURL=bento.js.map