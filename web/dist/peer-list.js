const escape = (value) => value.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
export function peerRankChange(items, selectedId, baseline) {
    const rows = items.filter(row => Number.isFinite(row.score)), own = rows.find(row => row.id === selectedId);
    const rank = own ? 1 + rows.filter(row => row.score > own.score + .005).length : null;
    const ids = (values) => values.filter(row => Number.isFinite(row.score)).map(row => row.id).sort().join('|');
    let change = null;
    const previous = baseline?.rows.filter(row => Number.isFinite(row.score));
    const prior = previous?.find(row => row.id === selectedId);
    const reference = baseline?.currentRows;
    const matches = !reference || (ids(reference) === ids(rows) && rows.every(row => { const saved = reference.find(r => r.id === row.id); return saved != null && Math.abs(saved.score - row.score) < .005; }));
    if (rank !== null && previous && prior && matches && ids(rows) === ids(previous))
        change = 1 + previous.filter(row => row.score > prior.score + .005).length - rank;
    return { rank, total: rows.length, change };
}
export function peerComparisonContext(items, selectedId, scope, baseline) {
    const { rank, total, change } = peerRankChange(items, selectedId, baseline);
    const own = items.find(row => row.id === selectedId);
    const title = `${own?.name ?? ''}${baseline ? ' · ' + baseline.label : ''}`;
    return `<div class="peer-comparison-context"><span>${escape(scope)}</span><span class="peer-own-rank" title="${escape(title)}"><span>Hạng <b>${rank === null ? '—' : `${rank}/${total}`}</b></span>${change === null ? '' : `<span aria-hidden="true">·</span><span class="${change > 0 ? 'peer-rank-up' : change < 0 ? 'peer-rank-down' : 'peer-rank-neutral'}">${change === 0 ? 'Không đổi' : `${change > 0 ? '↑' : '↓'} ${Math.abs(change)} bậc`}</span>`}</span></div>`;
}
export function renderPeerList(items, selectedId) {
    const rows = items.filter(item => Number.isFinite(item.score)).sort((a, b) => b.score - a.score || a.name.localeCompare(b.name, 'vi'));
    const html = rows.map((item, index) => {
        return `<div class="peer-row ${item.id === selectedId ? 'mine' : ''}"${item.id === selectedId ? ' aria-current="true"' : ''}><small class="peer-index">${index + 1}</small><span>${escape(item.name)}</span><b class="num">${item.score.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</b></div>`;
    }).join('');
    return `<div class="nearby-list" tabindex="0" role="region" aria-label="Danh sách điểm các cơ quan, đơn vị cùng cấp"><div class="peer-list-columns" aria-hidden="true"><span>STT</span><span>Cơ quan, đơn vị</span><span>Điểm</span></div>${html}</div>`;
}
/** Scroll only this list, never the page/sidebar; keep the score order intact. */
export function centerPeerLists(root) {
    root.querySelectorAll('.comparison-card .nearby-list').forEach(list => {
        const selected = list.querySelector('.peer-row.mine');
        if (!selected || list.clientHeight <= 0)
            return;
        const row = selected.getBoundingClientRect(), box = list.getBoundingClientRect();
        const target = list.scrollTop + row.top - box.top - list.clientTop + (row.height - list.clientHeight) / 2;
        list.scrollTop = Math.max(0, Math.min(target, list.scrollHeight - list.clientHeight));
    });
}
//# sourceMappingURL=peer-list.js.map