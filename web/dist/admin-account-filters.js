export function filterAdminAccounts(accounts, search, province, unit) {
    const query = search.trim().toLocaleLowerCase("vi");
    return accounts.filter(a => (!province || a.provinceId === province) && (!unit || a.unitId === unit) &&
        `${a.email ?? ""} ${a.name} ${a.provinceName ?? ""} ${a.unitName ?? ""}`.toLocaleLowerCase("vi").includes(query));
}
export function accountUnitOptions(accounts, province) {
    const units = new Map(accounts.filter(a => a.provinceId === province && a.unitId).map(a => [a.unitId, a.unitName ?? "Chưa xác định cơ quan"]));
    return [...units].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name, "vi"));
}
//# sourceMappingURL=admin-account-filters.js.map