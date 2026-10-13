export function filterAdminAccounts(accounts, search, province, unit) {
    const query = search.trim().toLocaleLowerCase("vi");
    return accounts.filter(a => (!province || a.provinceId === province) && (!unit || a.unitId === unit) &&
        `${a.email ?? ""} ${a.name} ${a.provinceName ?? ""} ${a.unitName ?? ""}`.toLocaleLowerCase("vi").includes(query));
}
export function accountUnitOptions(accounts, province) {
    const units = new Map(accounts.filter(a => a.provinceId === province && a.unitId).map(a => [a.unitId, a.unitName ?? "Chưa xác định cơ quan"]));
    return [...units].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name, "vi"));
}
export function accountPageQuery(page, search, province, unit, status) {
    const query = new URLSearchParams({ page: String(page) });
    if (search.trim())
        query.set('search', search.trim());
    if (province)
        query.set('provinceId', province);
    if (unit)
        query.set('unitId', unit);
    if (status)
        query.set('status', status);
    return query.toString();
}
export function accountPageSummary(page, total, totalAll) {
    const num = (n) => n.toLocaleString('vi-VN');
    const range = total ? `${num((page - 1) * 10 + 1)}–${num(Math.min(page * 10, total))}` : '0';
    return `Hiển thị ${range} / ${num(total)} tài khoản · Tổng toàn hệ thống: ${num(totalAll)}`;
}
export function accountPager(page, total) {
    const pages = Math.max(1, Math.ceil(total / 10));
    return `<button type="button" data-account-page="${page - 1}" ${page <= 1 ? 'disabled' : ''}>Trước</button><span>Trang ${page}/${pages}</span><button type="button" data-account-page="${page + 1}" ${page >= pages ? 'disabled' : ''}>Sau</button>`;
}
//# sourceMappingURL=admin-account-filters.js.map