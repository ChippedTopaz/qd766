const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export async function installTrialCreditManager(root, api, onChanged, deferLoad = false) {
    const policy = await api("access-policy");
    if (!policy.trialCreditManagement)
        return null;
    const section = document.createElement("section");
    section.innerHTML = `<h2>Quản lý Credit</h2><p>${policy.defaultCollectionAccess ? "Tài khoản dùng thử mặc định được tra cứu trong phạm vi được gán. " : ""}Credit cấp thêm được ghi vào sổ giao dịch.</p>${policy.localSimulation ? '<p><strong>Mô phỏng local — không đổi tài khoản hoặc credit production.</strong> <a href="/local-trial.html">Bàn thử nghiệm</a></p>' : ""}<form id="credit-form"><div class="form-grid"><label>Tài khoản<select id="credit-account" required></select></label><label ${policy.defaultCollectionAccess ? "hidden" : ""}>Quyền khai thác<select id="credit-permission"><option value="true">Cho phép yêu cầu TTHC</option><option value="false">Không cho phép yêu cầu mới</option></select></label><label>Cấp thêm credit<input id="credit-amount" type="number" min="0" max="100000" value="0" required></label><label>Lý do<input id="credit-reason" value="Cấp credit thử nghiệm" minlength="3" maxlength="240" required></label></div><div class="actions"><button class="primary" id="credit-save">Cấp Credit</button></div></form><p id="credit-message" role="status"></p><p id="credit-balance"></p><div class="scroll"><table><thead><tr><th>Giao dịch</th><th>Credit</th><th>Khả dụng sau</th><th>Đang giữ sau</th><th>Thời điểm</th></tr></thead><tbody id="credit-ledger"></tbody></table></div>`;
    root.append(section);
    section.querySelector(".form-grid")?.insertAdjacentHTML("afterbegin", '<label>Tìm tài khoản<input id="credit-search" type="search" maxlength="200" placeholder="Họ tên hoặc email" autocomplete="off"></label>');
    section.querySelector("#credit-form")?.insertAdjacentHTML("beforebegin", '<div class="actions"><button type="button" id="credit-prev">Trước</button><span id="credit-page" role="status"></span><button type="button" id="credit-next">Sau</button></div>');
    section.querySelector(".form-grid")?.insertAdjacentHTML("beforeend", '<label id="credit-source-label" hidden>Nguồn Credit<select id="credit-source"><option value="purchased">Credit mua riêng (mô phỏng)</option><option value="subscription">Credit subscription</option></select></label>');
    const get = (id) => section.querySelector(`#${id}`);
    let accounts = [], operationId = crypto.randomUUID(), inFlight = false, loading = false, read = 0, page = 1, totalPages = 1;
    let searchTimer;
    function updateBusy() {
        get("credit-save").disabled = inFlight || loading || !get("credit-account").value;
        get("credit-account").disabled = inFlight || loading;
        get("credit-prev").disabled = inFlight || loading || page <= 1;
        get("credit-next").disabled = inFlight || loading || page >= totalPages;
        get("credit-search").disabled = inFlight;
    }
    const labels = { topup: "Cấp Credit", grant: "Cấp Credit", reserve: "Giữ Credit", charge: "Thu Credit", release: "Hoàn Credit", refund: "Hoàn Credit", expire: "Hết hạn", redemption: "Đổi Credit gia hạn", adjustment: "Điều chỉnh" };
    async function ledger() { const id = get("credit-account").value, sequence = read; if (!id)
        return; const body = await api(`admin/accounts/${id}/credits`); if (sequence !== read || id !== get("credit-account").value)
        return; get("credit-balance").textContent = `Khả dụng: ${body.availableCredits.toLocaleString("vi-VN")} · Đang giữ: ${body.reservedCredits.toLocaleString("vi-VN")}`; get("credit-ledger").innerHTML = body.items.map(r => `<tr><td>${esc(labels[r.type] ?? r.type)}</td><td>${r.amount.toLocaleString("vi-VN")}</td><td>${r.availableAfter.toLocaleString("vi-VN")}</td><td>${r.reservedAfter.toLocaleString("vi-VN")}</td><td>${new Date(r.at).toLocaleString("vi-VN")}</td></tr>`).join("") || '<tr><td colspan="5">Chưa có giao dịch.</td></tr>'; }
    async function selectAccount() { const a = accounts.find(a => a.id === get("credit-account").value); get("credit-permission").value = String(policy.defaultCollectionAccess || a?.canCollect || false); get("credit-source-label").hidden = a?.walletMode !== "sources"; operationId = crypto.randomUUID(); await ledger(); }
    async function refreshAccounts(target, requestedPage = 1) {
        const sequence = ++read, selected = target ?? get("credit-account").value;
        const query = new URLSearchParams({ page: String(requestedPage) });
        if (target)
            query.set("accountId", target);
        else {
            query.set("status", "active");
            query.set("search", get("credit-search").value.trim());
        }
        loading = true;
        updateBusy();
        try {
            const body = await api(`admin/accounts?${query}`);
            if (sequence !== read)
                return;
            if (target) {
                const account = body.items.find(a => a.id === target);
                if (!account)
                    throw new Error("Không tìm thấy tài khoản. Vui lòng tải lại danh sách.");
                if (!account.active || !account.admitted)
                    throw new Error("Tài khoản chưa hoạt động hoặc chưa được duyệt.");
                get("credit-search").value = account.email ?? account.name;
            }
            accounts = body.items.filter(a => a.active && a.admitted);
            page = body.page;
            totalPages = Math.max(1, Math.ceil(body.total / body.pageSize));
            get("credit-page").textContent = `Trang ${page}/${totalPages} · ${body.total.toLocaleString("vi-VN")} tài khoản`;
            get("credit-account").innerHTML = accounts.map(a => `<option value="${a.id}">${esc(a.name)}${a.email ? " · " + esc(a.email) : ""}</option>`).join("");
            if (accounts.some(a => a.id === selected))
                get("credit-account").value = selected;
            get("credit-message").textContent = accounts.length ? "" : "Không có tài khoản phù hợp.";
            get("credit-balance").textContent = "";
            get("credit-ledger").innerHTML = "";
            await selectAccount();
        }
        catch (e) {
            if (sequence !== read)
                return;
            accounts = [];
            get("credit-account").innerHTML = "";
            get("credit-balance").textContent = "";
            get("credit-ledger").innerHTML = "";
            throw e;
        }
        finally {
            if (sequence === read) {
                loading = false;
                updateBusy();
            }
        }
    }
    function error(e) { get("credit-message").textContent = e instanceof Error ? e.message : String(e); }
    get("credit-search").addEventListener("input", () => {
        clearTimeout(searchTimer);
        ++read;
        loading = true;
        updateBusy();
        searchTimer = setTimeout(() => { void refreshAccounts().catch(error); }, 250);
    });
    for (const [id, step] of [["credit-prev", -1], ["credit-next", 1]])
        get(id).addEventListener("click", () => {
            if (inFlight || loading)
                return;
            void refreshAccounts(undefined, page + step).catch(error);
        });
    get("credit-account").addEventListener("change", () => { void selectAccount().catch(error); });
    for (const id of ["credit-permission", "credit-amount", "credit-reason", "credit-source"])
        get(id).addEventListener("input", () => { operationId = crypto.randomUUID(); });
    get("credit-form").addEventListener("submit", event => { event.preventDefault(); if (inFlight || loading || !get("credit-account").value)
        return; const target = get("credit-account").value; inFlight = true; updateBusy(); void (async () => { try {
        await api(`admin/accounts/${target}/trial-credit`, { operationId, canCollect: policy.defaultCollectionAccess || get("credit-permission").value === "true", amount: Number(get("credit-amount").value), reason: get("credit-reason").value, ...(!get("credit-source-label").hidden ? { creditSource: get("credit-source").value } : {}) });
        get("credit-amount").value = "0";
        await refreshAccounts(target);
        get("credit-message").textContent = "Đã lưu. Người dùng tải lại trang để cập nhật số dư Credit.";
        await onChanged?.();
    }
    catch (e) {
        error(e);
    }
    finally {
        inFlight = false;
        updateBusy();
    } })(); });
    if (deferLoad)
        root.addEventListener("click", event => {
            if (inFlight || loading || !event.target.closest('[data-admin-section="credits"]'))
                return;
            void refreshAccounts().catch(error);
        });
    else
        await refreshAccounts();
    updateBusy();
    return { openAccount: async (id) => { if (inFlight)
            throw new Error("Vui lòng chờ giao dịch hiện tại hoàn tất."); clearTimeout(searchTimer); await refreshAccounts(id); get("credit-amount").value = "0"; } };
}
//# sourceMappingURL=trial-credit-admin.js.map