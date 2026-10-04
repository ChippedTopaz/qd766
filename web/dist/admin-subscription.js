const esc = (v) => v.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const date = (v) => esc(new Date(v).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }));
export function adminSubscriptionCell(value) {
    if (!value)
        return '<span class="muted">Chưa áp dụng</span>';
    const labels = { active: "Còn hiệu lực", scheduled: "Sắp bắt đầu", expired: "Đã hết hạn", none: "Chưa kích hoạt" };
    const colors = { active: ["#15803d", "#f0fdf4"], scheduled: ["#1d4ed8", "#eff6ff"], expired: ["#b91c1c", "#fef2f2"], none: ["#64748b", "#f8fafc"] };
    const [color, bg] = colors[value.state];
    const origin = { trial: "Dùng thử", paid: "Gói trả phí", redemption: "Gia hạn bằng Credit" }[value.origin ?? ""] ?? "";
    const boundary = value.state === "scheduled" && value.startsAt ? `Bắt đầu ${date(value.startsAt)}` : value.endsAt ? `Đến ${date(value.endsAt)}` : "";
    return `<span class="pill" style="color:${color};background:${bg}">${labels[value.state]}</span>${origin ? `<small style="display:block;margin-top:6px">${origin}</small>` : ""}${boundary ? `<small style="display:block;font-variant-numeric:tabular-nums">${boundary}</small>` : ""}`;
}
//# sourceMappingURL=admin-subscription.js.map