const escape = (value) => value.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
export function renderPeerList(items, selectedId) {
    const rows = items.filter(item => Number.isFinite(item.score)).sort((a, b) => b.score - a.score || a.name.localeCompare(b.name, 'vi'));
    let higher = 0;
    const html = rows.map(item => {
        while (higher < rows.length && rows[higher].score > item.score + .005)
            higher++;
        return `<div class="peer-row ${item.id === selectedId ? 'mine' : ''}"${item.id === selectedId ? ' aria-current="true"' : ''}><span>${escape(item.name)}</span><b class="num">${item.score.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</b><small>Hạng ${higher + 1}/${rows.length}</small></div>`;
    }).join('');
    return `<div class="nearby-list" tabindex="0" role="region" aria-label="Danh sách điểm các cơ quan, đơn vị cùng cấp">${html}</div>`;
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