const esc = (v) => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export async function installTrialCreditManager(root, api, onChanged) {
    const policy = await api("access-policy");
    if (!policy.trialCreditManagement)
        return null;
    const section = document.createElement("section");
    section.innerHTML = `<h2>Quản lý Credit</h2><p>${policy.defaultCollectionAccess ? "Tài khoản dùng thử mặc định được tra cứu trong phạm vi được gán. " : ""}Credit cấp thêm được ghi vào sổ giao dịch.</p>${policy.localSimulation ? '<p><strong>Mô phỏng local — không đổi tài khoản hoặc credit production.</strong> <a href="/local-trial.html">Bàn thử nghiệm</a></p>' : ""}<form id="credit-form"><div class="form-grid"><label>Tài khoản<select id="credit-account" required></select></label><label ${policy.defaultCollectionAccess ? "hidden" : ""}>Quyền khai thác<select id="credit-permission"><option value="true">Cho phép yêu cầu TTHC</option><option value="false">Không cho phép yêu cầu mới</option></select></label><label>Cấp thêm credit<input id="credit-amount" type="number" min="0" max="100000" value="0" required></label><label>Lý do<input id="credit-reason" value="Cấp credit thử nghiệm" minlength="3" maxlength="240" required></label></div><div class="actions"><button class="primary" id="credit-save">Cấp Credit</button></div></form><p id="credit-message" role="status"></p><p id="credit-balance"></p><div class="scroll"><table><thead><tr><th>Giao dịch</th><th>Credit</th><th>Khả dụng sau</th><th>Đang giữ sau</th><th>Thời điểm</th></tr></thead><tbody id="credit-ledger"></tbody></table></div>`;
    root.append(section);
    section.querySelector(".form-grid")?.insertAdjacentHTML("beforeend", '<label id="credit-source-label" hidden>Nguồn Credit<select id="credit-source"><option value="purchased">Credit mua riêng (mô phỏng)</option><option value="subscription">Credit subscription</option></select></label>');
    const get = (id) => section.querySelector(`#${id}`);
    let accounts = [], operationId = crypto.randomUUID(), inFlight = false;
    const labels = { topup: "Cấp Credit", grant: "Cấp Credit", reserve: "Giữ Credit", charge: "Thu Credit", release: "Hoàn Credit", refund: "Hoàn Credit", expire: "Hết hạn", redemption: "Đổi Credit gia hạn", adjustment: "Điều chỉnh" };
    async function ledger() { const id = get("credit-account").value; if (!id)
        return; const body = await api(`admin/accounts/${id}/credits`); get("credit-balance").textContent = `Khả dụng: ${body.availableCredits.toLocaleString("vi-VN")} · Đang giữ: ${body.reservedCredits.toLocaleString("vi-VN")}`; get("credit-ledger").innerHTML = body.items.map(r => `<tr><td>${esc(labels[r.type] ?? r.type)}</td><td>${r.amount.toLocaleString("vi-VN")}</td><td>${r.availableAfter.toLocaleString("vi-VN")}</td><td>${r.reservedAfter.toLocaleString("vi-VN")}</td><td>${new Date(r.at).toLocaleString("vi-VN")}</td></tr>`).join("") || '<tr><td colspan="5">Chưa có giao dịch.</td></tr>'; }
    async function selectAccount() { const a = accounts.find(a => a.id === get("credit-account").value); get("credit-permission").value = String(policy.defaultCollectionAccess || a?.canCollect || false); get("credit-source-label").hidden = a?.walletMode !== "sources"; operationId = crypto.randomUUID(); await ledger(); }
    async function refreshAccounts(target) { const selected = target ?? get("credit-account").value; accounts = (await api("admin/accounts")).filter(a => a.active && a.admitted); if (target && !accounts.some(a => a.id === target))
        throw new Error("Tài khoản chưa hoạt động hoặc chưa được duyệt."); get("credit-account").innerHTML = accounts.map(a => `<option value="${a.id}">${esc(a.name)}${a.email ? " · " + esc(a.email) : ""}</option>`).join(""); if (accounts.some(a => a.id === selected))
        get("credit-account").value = selected; await selectAccount(); }
    function error(e) { get("credit-message").textContent = e instanceof Error ? e.message : String(e); }
    get("credit-account").addEventListener("change", () => { void selectAccount().catch(error); });
    for (const id of ["credit-permission", "credit-amount", "credit-reason", "credit-source"])
        get(id).addEventListener("input", () => { operationId = crypto.randomUUID(); });
    get("credit-form").addEventListener("submit", event => { event.preventDefault(); if (inFlight)
        return; inFlight = true; const button = get("credit-save"); button.disabled = true; void (async () => { try {
        await api(`admin/accounts/${get("credit-account").value}/trial-credit`, { operationId, canCollect: policy.defaultCollectionAccess || get("credit-permission").value === "true", amount: Number(get("credit-amount").value), reason: get("credit-reason").value, ...(!get("credit-source-label").hidden ? { creditSource: get("credit-source").value } : {}) });
        get("credit-message").textContent = "Đã lưu. Người dùng tải lại trang để cập nhật số dư Credit.";
        get("credit-amount").value = "0";
        await refreshAccounts();
        await onChanged?.();
    }
    catch (e) {
        error(e);
    }
    finally {
        inFlight = false;
        button.disabled = false;
    } })(); });
    await refreshAccounts();
    return { openAccount: async (id) => { if (inFlight)
            throw new Error("Vui lòng chờ giao dịch hiện tại hoàn tất."); inFlight = true; get("credit-save").disabled = true; get("credit-account").disabled = true; try {
            await refreshAccounts(id);
            get("credit-message").textContent = "";
            get("credit-amount").value = "0";
        }
        finally {
            inFlight = false;
            get("credit-save").disabled = false;
            get("credit-account").disabled = false;
        } } };
}
//# sourceMappingURL=trial-credit-admin.js.map