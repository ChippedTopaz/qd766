const num = (n) => new Intl.NumberFormat("vi-VN").format(n);
export const walletDate = (value) => new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
const esc = (v) => v.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export function sourceLabel(source) {
    return { subscription: "Subscription", purchased: "Mua riêng", mixed: "Hai nguồn" }[source ?? ""] ?? "Thử nghiệm cũ";
}
export function renderSourceWallet(data) {
    if (data.walletMode !== "sources")
        return "";
    return `<section style="background:#f8faff;border:1px solid #e8ecff;border-radius:20px;padding:20px;margin:20px 0">
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:20px">
      <div><span class="muted">Credit subscription</span><h2 style="font-variant-numeric:tabular-nums">${num(data.subscriptionCredits ?? 0)}</h2><small>Hết hạn theo chu kỳ tháng</small></div>
      <div><span class="muted">Credit mua riêng</span><h2 style="font-variant-numeric:tabular-nums">${num(data.purchasedCredits ?? 0)}</h2><small>Cộng dồn, không hết hạn</small></div>
    </div><p>${data.subscriptionEndsAt ? `Subscription đến ${esc(walletDate(data.subscriptionEndsAt))}` : data.subscriptionState === "expired" ? '<span style="color:#b91c1c;background:#fef2f2;border-radius:999px;padding:4px 10px">Subscription đã hết hạn</span>' : data.subscriptionState === "scheduled" ? "Subscription chưa đến ngày bắt đầu" : "Chưa có subscription đang hiệu lực"}</p>
    ${data.subscriptionState === "expired" ? '<p class="muted">Dữ liệu đã khai thác vẫn khả dụng. Gia hạn để khai thác thêm.</p>' : ""}
    ${(data.creditExpirations ?? []).map(lot => `<p class="muted" style="font-variant-numeric:tabular-nums">${num(lot.amount)} Credit subscription hết hạn: ${esc(walletDate(lot.at))}</p>`).join("")}
    ${(data.legacyCredits ?? 0) > 0 ? `<p class="muted">${num(data.legacyCredits)} Credit thử nghiệm cũ được giữ riêng, không tính vào số dư hai nguồn.</p>` : ""}
    ${data.redemptionCost ? `<p>Đổi ${num(data.redemptionCost)} Credit mua riêng để gia hạn 1 tháng. Tháng quy đổi không cấp thêm Credit.</p><button class="btn" data-renew ${data.canRedeem ? "" : "disabled"}>Gia hạn bằng Credit</button>${!data.canRedeem ? '<small style="display:block;margin-top:8px">Chỉ khả dụng khi subscription hết hạn và đủ Credit mua riêng.</small>' : ""}<div data-renew-confirm hidden style="margin-top:16px"><p>Xác nhận sử dụng ${num(data.redemptionCost)} Credit mua riêng để gia hạn 1 tháng?</p><button class="btn primary" data-confirm-renew>Xác nhận gia hạn</button> <button class="btn" data-cancel-renew>Hủy</button></div>` : ""}
    <p data-renew-status role="status"></p>
  </section>`;
}
//# sourceMappingURL=source-wallet-ui.js.map