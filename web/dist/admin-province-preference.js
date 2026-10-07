const validProvince = (id) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
const key = (account) => account?.role === 'admin' && account.id ? 'qd766:last-province:' + account.id : null;
export function lastAdminProvince(account, store) {
    const name = key(account);
    if (!name)
        return null;
    try {
        const id = (store ?? globalThis.localStorage)?.getItem(name);
        return id && validProvince(id) ? id : null;
    }
    catch {
        return null;
    }
}
export function rememberAdminProvince(account, id, store) {
    const name = key(account);
    if (!name || !validProvince(id))
        return;
    try {
        (store ?? globalThis.localStorage)?.setItem(name, id);
    }
    catch { /* Storage blocked/full must never prevent loading. */ }
}
export function clearAdminProvince(account, store) {
    const name = key(account);
    if (!name)
        return;
    try {
        (store ?? globalThis.localStorage)?.removeItem(name);
    }
    catch { /* Preference only; no account or access-policy changes. */ }
}
//# sourceMappingURL=admin-province-preference.js.map