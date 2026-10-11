export const WATCH_LIMIT = 5;
const valid = (v) => typeof v === 'number' && Number.isFinite(v) && v >= 0;
export function similarReceived(snapshot, ownId, peerId) {
    if (snapshot.scope !== 'all')
        return null;
    const progress = snapshot.datasets.find(g => g.group === 'dvc-progress-tree');
    if (!progress)
        return null;
    const entities = [progress.root, ...progress.children];
    const own = entities.find(e => e.departmentId === ownId), peer = entities.find(e => e.departmentId === peerId);
    const a = own?.parameters.totalReceived, b = peer?.parameters.totalReceived;
    if (valid(a) && valid(b))
        return b >= a * .8 && b <= a * 1.2;
    const permitted = peer;
    return permitted?.similarReceivedVolume ?? null;
}
export function watchTone(value, baseline) {
    if (value == null || baseline == null || !Number.isFinite(value) || !Number.isFinite(baseline))
        return 'watch-missing';
    const delta = Math.round((value - baseline) * 100) / 100;
    return delta > 0 ? 'watch-higher' : delta < 0 ? 'watch-lower' : 'watch-equal';
}
async function watchRequest(provinceId, csrf, ids) {
    const response = await fetch('/api/v1/me/agency-watch' + (ids ? '' : '?province_id=' + encodeURIComponent(provinceId)), {
        cache: 'no-store', signal: AbortSignal.timeout(15000),
        ...(ids ? { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-QD766-CSRF': csrf ?? '' }, body: JSON.stringify({ provinceId, unitIds: ids }) } : {})
    });
    const body = await response.json();
    if (!response.ok)
        throw new Error(typeof body.detail === 'string' ? body.detail : 'Chưa đọc hoặc lưu được danh sách theo dõi.');
    if (!Array.isArray(body.unitIds) || body.unitIds.length > WATCH_LIMIT || body.unitIds.some((id) => typeof id !== 'string') || new Set(body.unitIds).size !== body.unitIds.length)
        throw new Error('Danh sách theo dõi trả về không hợp lệ.');
    return body.unitIds;
}
export const readWatch = (provinceId) => watchRequest(provinceId);
export function saveWatch(provinceId, ids, csrf) {
    if (ids.length > WATCH_LIMIT || new Set(ids).size !== ids.length)
        return Promise.reject(new Error('Chỉ chọn tối đa 5 cơ quan, không trùng nhau.'));
    return watchRequest(provinceId, csrf, ids);
}
//# sourceMappingURL=agency-watch.js.map