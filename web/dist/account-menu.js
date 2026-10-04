const esc = (v) => v.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
let menuEvents = null;
export function accountMenu(user) {
    const initials = user.name.trim().split(/\s+/).filter(Boolean).slice(-2).map(word => Array.from(word)[0]).join("").toUpperCase() || "TK";
    return `<style>
  .sidebar .account-zone{margin-top:auto;padding-top:16px;border-top:1px solid #edf0f8;position:relative;width:100%}
  .account-switch{width:100%;display:flex;gap:10px;align-items:center;text-align:left;border:0;border-radius:14px;background:#f5f6ff;padding:11px;cursor:pointer;color:#172554;font:inherit}
  .account-avatar{width:38px;height:38px;flex:0 0 38px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(135deg,#6366f1,#9333ea);color:white;font-weight:700;font-size:13px}
  .account-copy{min-width:0;flex:1}.account-copy strong,.account-copy small{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.account-copy strong{font-size:12px}.account-copy small{color:#64748b;font-size:11px;margin-top:3px;font-variant-numeric:tabular-nums}
  .account-popover{position:absolute;bottom:calc(100% + 8px);right:0;width:100%;box-sizing:border-box;max-width:calc(100vw - 24px);border:1px solid #e8eaf5;box-shadow:0 12px 40px #17255418;border-radius:16px;background:white;padding:8px;z-index:90}
  .account-popover[hidden]{display:none}.account-popover button{display:block;width:100%;border:0;background:none;padding:12px;border-radius:10px;text-align:left;font:inherit;font-size:13px;color:#334155;cursor:pointer}.account-popover button:hover{background:#f5f6ff}.account-popover button[data-action=logout]{color:#dc2626;border-top:1px solid #f1f5f9;border-radius:0 0 10px 10px}
  .account-switch:focus-visible,.account-popover button:focus-visible{outline:2px solid #6366f1;outline-offset:2px}
  @media(min-width:761px) and (max-width:1100px){.account-switch{padding:4px;justify-content:center}.account-copy,.account-switch>span:last-child{display:none}.account-popover{right:auto;left:0;width:240px}}
  @media(max-width:760px){.account-zone.account-mobile{position:relative;display:flex;justify-content:flex-end;background:#fff;padding:10px 14px;border-bottom:1px solid #edf0f8}.account-mobile .account-switch{width:min(100%,320px);padding:8px 10px}.account-avatar{width:32px;height:32px;flex-basis:32px;font-size:11px}.account-copy small{margin-top:0}.account-mobile .account-popover{bottom:auto;top:calc(100% + 4px);right:14px;width:min(320px,calc(100vw - 28px))}}
  </style><div class="account-zone"><button class="account-switch" data-account-toggle aria-expanded="false" aria-controls="account-popover"><span class="account-avatar" aria-hidden="true">${esc(initials)}</span><span class="account-copy"><strong>${esc(user.name)}</strong><small>${new Intl.NumberFormat("vi-VN").format(user.credits)} credit khả dụng</small></span><span aria-hidden="true">⌃</span></button><div id="account-popover" class="account-popover" hidden><button data-action="account-info">Thông tin tài khoản</button><button data-action="open-credits">Usage (credits)</button><button data-action="logout">Đăng xuất</button></div></div>`;
}
export function bindAccountMenu(user) {
    menuEvents?.abort();
    menuEvents = new AbortController();
    const toggle = document.querySelector("[data-account-toggle]");
    const popover = document.querySelector("#account-popover");
    if (!toggle || !popover)
        return;
    const zone = toggle.closest(".account-zone");
    const sidebar = document.querySelector(".sidebar"), workspace = document.querySelector(".workspace");
    const mobile = window.matchMedia("(max-width:760px)");
    const position = () => {
        if (!zone || !sidebar || !workspace)
            return;
        zone.classList.toggle("account-mobile", mobile.matches);
        if (mobile.matches)
            workspace.prepend(zone);
        else
            sidebar.append(zone);
        popover.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
    };
    position();
    mobile.addEventListener("change", position, { signal: menuEvents.signal });
    const close = () => { popover.hidden = true; toggle.setAttribute("aria-expanded", "false"); };
    toggle.addEventListener("click", () => { popover.hidden = !popover.hidden; toggle.setAttribute("aria-expanded", String(!popover.hidden)); if (!popover.hidden)
        popover.querySelector("button")?.focus(); });
    document.addEventListener("click", event => { if (!(event.target instanceof Node) || !toggle.closest(".account-zone")?.contains(event.target))
        close(); }, { signal: menuEvents.signal });
    document.addEventListener("keydown", event => { if (event.key === "Escape" && !popover.hidden) {
        close();
        toggle.focus();
    } }, { signal: menuEvents.signal });
    popover.addEventListener("click", close);
    popover.querySelector("[data-action=account-info]")?.addEventListener("click", () => {
        const dialog = document.createElement("dialog");
        dialog.setAttribute("aria-label", "Thông tin tài khoản");
        dialog.style.cssText = "width:min(460px,92vw);border:1px solid #e2e8f0;border-radius:24px;padding:28px;background:white;color:#0f172a";
        dialog.innerHTML = `<h2>Thông tin tài khoản</h2><dl style="line-height:1.8;overflow-wrap:anywhere"><dt class="muted">Họ tên</dt><dd style="margin:0 0 16px">${esc(user.name)}</dd><dt class="muted">Email</dt><dd style="margin:0 0 16px">${esc(user.email ?? "Chưa cập nhật")}</dd><dt class="muted">Vai trò</dt><dd style="margin:0 0 16px">${user.role === "admin" ? "Quản trị viên" : "Người dùng"}</dd><dt class="muted">Phạm vi truy cập</dt><dd style="margin:0 0 16px">${user.accessTier === "national" ? "Toàn quốc" : user.accessTier === "province" ? "Tỉnh và các cơ quan trực thuộc" : "Cơ quan được gán"}</dd><dt class="muted">Khai thác TTHC</dt><dd style="margin:0 0 16px">${user.canCollect ? "Được phép" : "Chưa được cấp quyền"}</dd></dl><button class="btn" data-close>Đóng</button>`;
        document.body.append(dialog);
        dialog.showModal();
        dialog.querySelector("[data-close]")?.addEventListener("click", () => dialog.close());
        dialog.addEventListener("close", () => { dialog.remove(); toggle.focus(); });
    });
}
//# sourceMappingURL=account-menu.js.map