export function scoreDetailAllowed(target, access) {
    if (target.group !== null && !access.groupIds.includes(target.group))
        return false;
    if (target.reportDate && (target.scope !== 'all' || !/^\d{4}-\d{2}-\d{2}$/.test(target.reportDate)))
        return false;
    if (target.provinceId !== access.provinceId)
        return target.scope === 'all' && target.unitId === target.provinceId &&
            (access.role === 'admin' || access.accessTier === 'national') && access.availableProvinceIds.includes(target.provinceId);
    return access.unitIds.includes(target.unitId) && !(access.accessTier === 'agency' && access.role !== 'admin' && target.unitId !== access.assignedUnitId);
}
const esc = (v) => v.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export function renderScoreDetailLink(value, key, label) {
    if (value == null || !Number.isFinite(value))
        return '—';
    const text = value.toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return key ? `<button type="button" class="score-detail-link" data-score-detail="${esc(key)}" title="${esc(label)}" aria-label="${esc(label)}">${text}</button>` : text;
}
//# sourceMappingURL=score-drilldown.js.map