const escape = (value) => value.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
export function renderPeerList(items, selectedId) {
    const rows = [...items].sort((a, b) => b.score - a.score || a.name.localeCompare(b.name, 'vi'));
    let higher = 0;
    const html = rows.map(item => {
        while (higher < rows.length && rows[higher].score > item.score + .005)
            higher++;
        return `<div class="peer-row ${item.id === selectedId ? 'mine' : ''}"><span>${escape(item.name)}</span><b class="num">${item.score.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</b><small>Hạng ${higher + 1}</small></div>`;
    }).join('');
    return `<div class="nearby-list" tabindex="0" role="region" aria-label="Danh sách điểm các cơ quan, đơn vị cùng cấp">${html}</div>`;
}
//# sourceMappingURL=peer-list.js.map