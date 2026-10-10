const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const labels = { queued: "Đang chờ", running: "Đang chạy", succeeded: "Thành công", failed: "Thất bại", halted: "Tạm dừng", SUCCESS: "Thành công", FAILED: "Thất bại", HALTED: "Tạm dừng", RUNNING: "Đang chạy", COMPLETE: "Hoàn tất", INCOMPLETE: "Chưa hoàn tất", UNAVAILABLE: "Chưa đọc được", paused: "Tạm dừng" };
const state = (value) => `<span class="collection-state state-${esc(value.toLowerCase())}">${esc(labels[value] ?? value)}</span>`;
const num = (v) => new Intl.NumberFormat("vi-VN").format(v);
const at = (v) => v ? esc(new Date(v).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })) : "—";
export const collectionPeriod = (p) => p.type === "month" ? `Tháng ${p.month}/${p.year}` : p.type === "quarter" ? `Quý ${p.quarter}/${p.year}` : p.year ? `Năm ${p.year}` : "—";
function phaseName(value) { if (value === "national")
    return "Tổng hợp toàn quốc"; const [type, year, v] = value.split("-"); return collectionPeriod({ type: type ?? "", year: Number(year), month: Number(v), quarter: Number(v) }); }
function progress(done, total) { const percent = total > 0 ? Math.min(100, Math.max(0, done / total * 100)) : 0; return `<div class="collection-progress"><span>${num(done)} / ${num(total)}</span><progress value="${percent}" max="100" aria-label="${num(done)} trên ${num(total)}"></progress></div>`; }
export function renderCollectionJobs(report, mode) {
    const paused = report.control.state === 'open';
    return `<h3>${mode === 'user' ? 'Yêu cầu tra cứu' : 'Lượt khai thác hệ thống'}</h3><div class="scroll"><table class="collection-jobs-table"><thead><tr><th>Loại</th><th>Người yêu cầu</th><th>Tỉnh</th><th>Thủ tục</th><th>Kỳ</th><th>Trạng thái</th><th>Nhóm cần lấy</th><th>Lượt xử lý</th><th>Tạo yêu cầu</th><th>Cập nhật</th></tr></thead><tbody>${report.jobs.length ? report.jobs.map(j => {
        const full = (j.formalityName ?? j.formalityId ?? 'Tất cả TTHC').replace(' · ', ' - ');
        const short = full.length > 64 ? full.slice(0, 61) + '…' : full;
        return `<tr><td>${j.kind === 'formality' ? 'Theo TTHC' : 'Mặc định'}</td><td>${esc(j.requestedBy?.join(', ') || 'Hệ thống / quản trị')}</td><td>${esc(j.province)}</td><td class="collection-formality" title="${esc(full)}">${esc(short)}</td><td>${esc(collectionPeriod(j.period))}</td><td>${state(paused && ['queued', 'running'].includes(j.state) ? 'paused' : j.state)}</td><td>${num(j.expectedGroups)}</td><td>${num(j.attempts)}</td><td>${at(j.createdAt)}</td><td>${at(j.updatedAt)}</td></tr>`;
    }).join('') : '<tr><td colspan="10">Chưa có yêu cầu phù hợp.</td></tr>'}</tbody></table></div>`;
}
export function renderCollectionReport(report, mode = 'all') {
    if (mode === 'user')
        return `<div class="collection-stats">${['queued', 'running', 'succeeded', 'failed', 'halted'].map(key => `<article><small>${labels[key]}</small><strong>${num(report.counts[key] ?? 0)}</strong></article>`).join('')}</div>${renderCollectionJobs(report, mode)}`;
    const paused = report.control.state === "open";
    const probe = report.probe;
    const html = `${report.localSimulation ? '<p class="collection-notice">Yêu cầu bên dưới thuộc môi trường mô phỏng. Đợt kiểm chứng dữ liệu thật được hiển thị riêng và chỉ cho phép xem.</p>' : ""}
 <div class="collection-stats">${["queued", "running", "succeeded", "failed", "halted"].map(key => `<article><small>${labels[key]}</small><strong>${num(report.counts[key] ?? 0)}</strong></article>`).join("")}</div>
 <p class="collection-notice">Bộ thu thập: ${paused ? "Tạm dừng nhận việc" : "Sẵn sàng"}${paused ? ` · ${esc(report.control.reason === "operator-requested-pause" ? "Theo yêu cầu quản trị" : report.control.reason ?? "Cần kiểm tra")}` : ""}. Nhật ký này chỉ đọc, không thay đổi hàng chờ hoặc Credit.</p>
 ${probe ? `<div class="collection-probe"><h3>${esc(probe.label)} ${state(probe.state)}</h3><div class="scroll"><table><thead><tr><th>Kỳ</th><th>Tiến độ</th><th>Đang chạy</th><th>Thất bại / tạm dừng</th></tr></thead><tbody>${probe.phases.map(p => `<tr><td>${esc(phaseName(p.period))}</td><td>${progress(p.counts.SUCCESS ?? 0, p.total)}</td><td>${num(p.counts.RUNNING ?? 0)}</td><td>${num((p.counts.FAILED ?? 0) + (p.counts.HALTED ?? 0))}</td></tr>`).join("")}</tbody></table></div>${probe.errors.length ? `<p class="collection-error">${probe.errors.map(e => esc(`${phaseName(e.phase)} · ${e.province ?? ""} · ${e.error ?? "Cần kiểm tra"}`)).join("<br>")}</p>` : ""}</div>` : ""}
 <h3>Lịch làm mới hằng ngày · 05:00</h3><p>Ngày báo cáo là ngày trước đợt thu thập. Tiến độ tính theo 102 khối tỉnh–kỳ.</p><div class="scroll"><table><thead><tr><th>Ngày báo cáo</th><th>Trạng thái</th><th>Khối hoàn tất</th><th>Khối lỗi</th><th>Lưu ý</th></tr></thead><tbody>${report.daily?.length ? report.daily.map(run => `<tr><td>${esc(run.reportDate.split("-").reverse().join("/"))}</td><td>${state(run.state === "COMPLETE" ? "succeeded" : run.state === "RUNNING" ? "running" : run.state === "HALTED" ? "halted" : "failed")}</td><td>${progress(run.completed, run.expected)}</td><td>${num(run.failures.length)}</td><td>${run.failures.map(f => esc((f.province ?? "Tổng hợp") + " · " + (f.error ?? f.state))).join("<br>") || "—"}</td></tr>`).join("") : '<tr><td colspan="5">Chưa có đợt chạy theo lịch 05:00 mới.</td></tr>'}</tbody></table></div>
 <h3>Đợt cập nhật mặc định</h3><div class="scroll"><table><thead><tr><th>Kỳ</th><th>Trạng thái</th><th>Tỉnh hoàn tất</th><th>Thất bại</th><th>Cập nhật</th></tr></thead><tbody>${report.batches.length ? report.batches.map(b => `<tr><td>${esc(collectionPeriod(b.period))}</td><td>${state(paused && ["queued", "running"].includes(b.state) ? "paused" : b.state)}</td><td>${progress(b.completed + b.skipped, b.total)}</td><td>${num(b.failed)}</td><td>${at(b.updatedAt)}</td></tr>`).join("") : '<tr><td colspan="5">Chưa có đợt cập nhật.</td></tr>'}</tbody></table></div>
 ${renderCollectionJobs(report, mode)}`;
    return html;
}
export function installCollectionMonitor(root, api) {
    installCollectionPanel(root, api, 'system');
    installCollectionPanel(root, api, 'user');
}
function installCollectionPanel(root, api, mode) {
    const section = document.createElement("section");
    section.dataset.collectionMonitor = "true";
    const panelKey = 'collection';
    section.dataset.collectionSource = mode;
    section.innerHTML = `<div class="collection-toolbar"><div><h2>Nhật ký khai thác</h2><p>Tiến trình cập nhật và yêu cầu tra cứu dữ liệu.</p></div><button data-log-refresh>Làm mới</button></div><div class="collection-filters"><label>Loại yêu cầu<select data-log-kind><option value="">Tất cả</option><option value="default">Dữ liệu mặc định</option><option value="formality">Theo TTHC</option></select></label><label>Trạng thái<select data-log-state><option value="">Tất cả</option>${["queued", "running", "succeeded", "failed", "halted"].map(s => `<option value="${s}">${labels[s]}</option>`).join("")}</select></label></div><p data-log-message role="status">Chọn Nhật ký khai thác để xem.</p><div data-log-body></div><div class="actions"><button data-log-prev>Trang trước</button><span data-log-page></span><button data-log-next>Trang sau</button></div>`;
    root.append(section);
    section.querySelector('h2').textContent = mode === 'system' ? 'Nhật ký hệ thống' : 'Yêu cầu tra cứu';
    section.querySelector('.collection-toolbar p').textContent = mode === 'system' ? 'Lịch sử khai thác định kỳ và các lượt khai thác do quản trị thực hiện.' : 'Lịch sử yêu cầu tra cứu dữ liệu của người dùng.';
    section.querySelector('[data-log-message]').textContent = 'Chọn menu để xem nhật ký.';
    let offset = 0, total = 0, inFlight = false;
    const message = section.querySelector("[data-log-message]");
    const prev = section.querySelector("[data-log-prev]"), next = section.querySelector("[data-log-next]");
    async function refresh() {
        if (inFlight)
            return;
        inFlight = true;
        try {
            const params = new URLSearchParams({ offset: String(offset), limit: "30", source: mode });
            for (const [key, selector] of [["kind", "[data-log-kind]"], ["state", "[data-log-state]"]]) {
                const value = section.querySelector(selector).value;
                if (value)
                    params.set(key, value);
            }
            const report = await api(`admin/collection-log?${params}`);
            total = report.total;
            section.querySelector("[data-log-body]").innerHTML = renderCollectionReport(report, mode);
            section.querySelector("[data-log-page]").textContent = `${num(total)} yêu cầu · Trang ${Math.floor(offset / 30) + 1}`;
            prev.disabled = offset === 0;
            next.disabled = offset + 30 >= total;
            message.textContent = `Cập nhật ${new Date().toLocaleTimeString("vi-VN")} · Tự làm mới mỗi 5 giây khi đang xem.`;
        }
        catch (error) {
            message.textContent = error instanceof Error ? error.message : "Không đọc được nhật ký.";
        }
        finally {
            inFlight = false;
        }
    }
    section.querySelector("[data-log-refresh]").addEventListener("click", () => void refresh());
    section.querySelectorAll("select").forEach(select => select.addEventListener("change", () => { offset = 0; void refresh(); }));
    prev.addEventListener("click", () => { offset = Math.max(0, offset - 30); void refresh(); });
    next.addEventListener("click", () => { if (offset + 30 < total) {
        offset += 30;
        void refresh();
    } });
    root.addEventListener("click", event => { const target = event.target; if (!section.hidden && (target.closest(`[data-admin-section="${panelKey}"]`) || target.closest(`[data-collection-tab="${mode}"]`)))
        void refresh(); });
    window.setInterval(() => { const panel = section.closest(`[data-admin-panel="${panelKey}"]`); if (panel && !panel.hidden && !section.hidden && document.visibilityState === "visible")
        void refresh(); }, 5000);
}
//# sourceMappingURL=admin-collection.js.map