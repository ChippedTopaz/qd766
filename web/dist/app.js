import { allUnitTotals, buildSuggestions, buildUnitView, immediatePeers, peerStats, previousAvailablePeriod, similarVolumePeers, snapshotFor, snapshotForUnit, snapshotKey } from "./analytics.js";
import { analyzeOnlineScore, ONLINE_SCORING_PROFILE } from "./online-scoring.js";
import { analyzeProgressScore } from "./progress-scoring.js";
import { analysisExcelFilename, buildAnalysisWorkbook } from "./excel-export.js";
import { buildLeadershipReport, buildLeadershipWorkbook, leadershipColors, leadershipUpdatedLabel } from "./leadership-report.js";
import { parameterLabels } from "./parameter-labels.js";
const root = document.querySelector("#app");
if (!root)
    throw new Error("Thiếu app root");
const screens = [
    { id: "overview", label: "Tổng quan", icon: "⌂" }, { id: "time", label: "Theo thời gian", icon: "↗" },
    { id: "peers", label: "Trong tỉnh", icon: "≋" }, { id: "procedure", label: "Theo TTHC", icon: "▦" },
    { id: "suggestions", label: "Gợi ý", icon: "◇" }, { id: "quality", label: "Chất lượng dữ liệu", icon: "✓" },
    { id: "operations", label: "Vận hành", icon: "⚙" },
];
let publicReadOnly = false;
let loginRequired = false;
let googleLoginEnabled = false;
let signedInUser = null;
let data;
let state;
let selectionRequest = 0;
let pendingMessage = "";
let completionMessage = "";
let pendingProvinceId = "";
let searchableSelects = [];
let operationData = { loading: false, error: null, circuitState: "unknown", circuitReason: null, snapshotCount: 0, latestSnapshotAt: null, jobs: [], batches: [], provinceBatches: [] };
let provinceOptions = [];
let provinceBenchmarks = {};
const benchmarkLoading = new Set();
let catalogPreview = { loading: false, error: null, level: "", field: "", query: "", fields: [], selected: 0, available: 0, missing: 0, items: [], selectedId: null, offset: 0, mode: "single" };
let catalogPreviewRequest = 0;
let catalogSearchTimer = 0;
const catalogProvinceCode = () => data.province.code ?? provinceOptions.find(item => item.id === data.province.id)?.provinceCode ?? "";
const initialPeriodFor = (loaded) => [...loaded.periods].reverse().find(item => item.type === "year" && Boolean(loaded.snapshots[`${item.id}:all`])) ?? [...loaded.periods].reverse().find(item => Boolean(loaded.snapshots[`${item.id}:all`]));
function normalizeLoadedData(loaded) {
    if (loaded.formality.id) {
        for (const item of loaded.periods) {
            const legacyKey = `${item.id}:formality`;
            if (loaded.snapshots[legacyKey]) {
                loaded.snapshots[snapshotKey(item.id, "formality", loaded.formality.id)] = loaded.snapshots[legacyKey];
                delete loaded.snapshots[legacyKey];
            }
        }
    }
    for (const item of loaded.periods) {
        const legacy = item;
        if (item.value === undefined)
            item.value = legacy.month ?? legacy.quarter ?? null;
        item.provisional = Boolean(item.provisional);
    }
    const discovered = new Map();
    for (const snap of Object.values(loaded.snapshots)) {
        for (const dataset of snap.datasets) {
            dataset.capture ??= { capturedAt: "", httpStatus: 200, contentType: "application/json", bytes: 0 };
            for (const entity of [dataset.root, ...dataset.children]) {
                entity.metrics ??= [];
                entity.parameters ??= {};
                discovered.set(entity.departmentId, { departmentId: entity.departmentId, departmentName: entity.departmentName, departmentType: entity.departmentType, departmentLevel: entity === dataset.root ? "PROVINCE_TOTAL" : entity.departmentLevel });
            }
        }
    }
    if (!Array.isArray(loaded.units) || !loaded.units.length)
        loaded.units = [...discovered.values()];
    if (!loaded.defaultUnitId)
        loaded.defaultUnitId = loaded.province.id;
    if (!Array.isArray(loaded.metricCatalog))
        loaded.metricCatalog = [];
    return loaded;
}
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char] ?? char);
const n = (value, digits = 2) => value === null || value === undefined || !Number.isFinite(value) ? "N/A" : value.toLocaleString("vi-VN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const int = (value) => value === null || value === undefined || !Number.isFinite(value) ? "N/A" : value.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
const pct = (value) => value === null || value === undefined ? "N/A" : `${n(value, 1)}%`;
const dateTime = (value) => {
    if (!value)
        return "Chưa xác định";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });
};
const period = () => data.periods.find((item) => item.id === state.periodId) ?? data.periods[0];
const snapshot = (scope = state.scope) => snapshotFor(data, state.periodId, scope);
const unit = (scope = state.scope) => buildUnitView(data, state.periodId, scope, state.unitId);
const scoreValue = (group) => group.score.kind === "VALID_NUMBER" || group.score.kind === "ZERO_VALUE" ? group.score.value : null;
const level = (ratio) => ratio === null ? ["Không có dữ liệu", "neutral"] : ratio >= 90 ? ["Tốt", "good"] : ratio >= 70 ? ["Cần theo dõi", "warn"] : ["Cần cải thiện", "bad"];
const title = (name, description, note = "") => `<header class="page-head"><div><p class="eyebrow">${esc(data.province.name)} · ${esc(period().label)}</p><h1>${esc(name)}</h1><p>${esc(description)}</p></div>${note ? `<div class="head-note muted">${note}</div>` : ""}</header>`;
const rankText = (view) => view.peer ? `Hạng ${view.peer.rank}/${view.peer.total}${view.peer.tiedCount > 1 ? ` · đồng hạng ${view.peer.tiedCount}` : ""}` : "Chưa xếp hạng";
const periodOrder = (item) => item.type === "month" ? item.year * 12 + (item.value ?? 0) : item.type === "quarter" ? item.year * 4 + (item.value ?? 0) : item.year;
function previousPeriodFor(periodId = state.periodId) {
    return previousAvailablePeriod(data, periodId, state.scope);
}
const benchmarkCacheKey = (periodId) => `${periodId}:${state.scope}:${state.scope === "formality" ? data.formality.id : "all"}`;
function benchmarkRank(periodId, groupId, rootId = state.unitId) {
    const rows = provinceBenchmarks[benchmarkCacheKey(periodId)] ?? [];
    const current = rows.find(item => item.rootDepartmentId === rootId);
    const value = groupId ? current?.groups[groupId]?.score : current?.totalScore;
    if (value === null || value === undefined)
        return null;
    const values = rows.flatMap(item => { const candidate = groupId ? item.groups[groupId]?.score : item.totalScore; return candidate === null || candidate === undefined ? [] : [candidate]; });
    if (values.length < 2)
        return null;
    return peerStats(values, value);
}
function rankFor(view, periodId, groupId) {
    const selected = data.units.find(item => item.departmentId === state.unitId);
    return selected?.departmentLevel === "PROVINCE_TOTAL" ? benchmarkRank(periodId, groupId) : view.peer;
}
const alphabet = new Intl.Collator("vi", { sensitivity: "base", numeric: true });
const displayProvinceName = (value) => value.replace(/^UBND\s+(tỉnh|thành phố)\s+/i, "");
const byName = (left, right) => alphabet.compare(left.departmentName, right.departmentName);
const unitOptions = () => {
    const groups = [
        { label: "Kết quả chung toàn tỉnh", items: data.units.filter(item => item.departmentId === data.province.id) },
        { label: "Sở, ban, ngành", items: data.units.filter(item => item.departmentId !== data.province.id && item.departmentLevel === "PROVINCE") },
        { label: "Xã, phường", items: data.units.filter(item => item.departmentLevel === "COMMUNE") },
    ];
    return groups.map(group => `<optgroup label="${group.label}">${group.items.sort(byName).map(item => `<option value="${esc(item.departmentId)}" ${item.departmentId === state.unitId ? "selected" : ""}>${esc(item.departmentName)}</option>`).join("")}</optgroup>`).join("");
};
function nav() {
    return `<aside class="sidebar"><div class="brand"><span class="brand-mark">766</span><span><strong>Phân tích QĐ766</strong><small>Phục vụ cơ quan hành chính</small></span></div><div class="nav-label">Không gian làm việc</div><nav class="nav" aria-label="Điều hướng chính">${screens.filter(item => !publicReadOnly || !["procedure", "operations", "suggestions"].includes(item.id)).map((item) => `<button data-nav="${item.id}" class="${state.screen === item.id ? "active" : ""}" aria-current="${state.screen === item.id ? "page" : "false"}"><span class="nav-icon" aria-hidden="true">${item.icon}</span><span>${item.label}</span></button>`).join("")}</nav><div class="side-meta"><div><span class="sync-dot"></span>Dữ liệu đã cập nhật</div><div>Toàn tỉnh · Sở, ngành · Xã, phường</div><div>Kết quả từ hệ thống công bố</div></div></aside>`;
}
function context() {
    const selectedPeriod = period();
    const sameType = data.periods.filter(item => item.type === selectedPeriod.type && item.year === selectedPeriod.year);
    const years = [...new Set(data.periods.map(item => item.year))].sort((a, b) => b - a);
    const formalityScopeLabel = catalogPreview.mode === "single" && catalogPreview.selectedId ? `${data.formality.code} · ${data.formality.name}` : catalogPreview.mode === "filtered" && catalogPreview.selected ? `${int(catalogPreview.selected)} TTHC sau lọc` : "Theo thủ tục hành chính";
    const canSubmit = state.scope === "formality" && state.demo === "ready" && (catalogPreview.mode === "filtered" ? catalogPreview.selected > 0 : Boolean(catalogPreview.selectedId));
    const selectedProvinceId = pendingProvinceId || data.province.id;
    const provinceItems = (provinceOptions.length ? provinceOptions : [{ id: data.province.id, name: data.province.name, departmentCode: null, provinceCode: data.province.code ?? null, snapshotCount: 0, latestSnapshotAt: null, available: true }]).slice().sort((left, right) => alphabet.compare(displayProvinceName(left.name), displayProvinceName(right.name))).map(item => `<option value="${esc(item.id)}" ${item.id === selectedProvinceId ? "selected" : ""}>${esc(displayProvinceName(item.name))}${item.available ? "" : " · chưa có dữ liệu"}</option>`).join("");
    return `<header class="contextbar"><div class="context-fields"><label class="field province"><span>Tỉnh/Thành phố</span><select id="province-select">${provinceItems}</select></label><label class="field unit"><span>Cơ quan, đơn vị</span><select id="unit-select">${unitOptions()}</select></label><label class="field compact"><span>Loại kỳ</span><select id="period-type"><option value="month" ${selectedPeriod.type === "month" ? "selected" : ""}>Tháng</option><option value="quarter" ${selectedPeriod.type === "quarter" ? "selected" : ""}>Quý</option><option value="year" ${selectedPeriod.type === "year" ? "selected" : ""}>Năm</option></select></label><label class="field compact"><span>Kỳ cụ thể</span><select id="period-value">${sameType.map(item => `<option value="${item.id}" ${item.id === state.periodId ? "selected" : ""}>${item.type === "month" ? `Tháng ${item.value}` : item.type === "quarter" ? `Quý ${item.value}` : "Cả năm"}</option>`).join("")}</select></label><label class="field compact"><span>Năm</span><select id="report-year">${years.map(year => `<option value="${year}" ${year === selectedPeriod.year ? "selected" : ""}>${year}</option>`).join("")}</select></label><label class="field"><span>Phạm vi thủ tục</span><select id="scope-select"><option value="all" ${state.scope === "all" ? "selected" : ""}>Tất cả thủ tục hành chính</option>${publicReadOnly ? "" : `<option value="formality" ${state.scope === "formality" ? "selected" : ""}>${esc(formalityScopeLabel)}</option>`}</select></label></div><div class="context-actions">${signedInUser ? `<span class="muted">${esc(signedInUser.name)}</span><button class="btn" data-action="logout">Đăng xuất</button>` : googleLoginEnabled ? `<a class="btn" href="/api/v1/auth/google/start">Đăng nhập Google</a>` : ""}${canSubmit ? `<button class="btn primary" data-action="submit-statistics">Thống kê</button>` : ""}<button class="btn" data-action="open-quality">${data.snapshots[snapshotKey(state.periodId, state.scope, data.formality.id)]?.delivery?.detailsAvailable === false ? "● Chỉ có điểm tổng hợp" : "● Chất lượng dữ liệu"}</button><button class="btn" data-action="export">Xuất dữ liệu</button><button class="btn primary" data-action="brief">Báo cáo lãnh đạo</button></div></header>`;
}
function shell(content) {
    const loaded = data.snapshots[snapshotKey(state.periodId, state.scope, data.formality.id)];
    const formalityNotice = state.scope === "formality" && catalogPreview.mode === "single" && catalogPreview.selectedId ? `<div class="formality-notice" role="status"><strong>Thủ tục đang chọn</strong><span><b>${esc(data.formality.code)}</b>${esc(data.formality.name)}</span></div>` : state.scope === "formality" && catalogPreview.mode === "filtered" && catalogPreview.selected > 0 ? `<div class="formality-notice batch" role="status"><strong>Phạm vi đang chọn</strong><span><b>${int(catalogPreview.selected)} TTHC</b>${catalogPreview.level === "ward" ? "Cấp xã" : catalogPreview.level === "province" ? "Cấp tỉnh" : "Cấp tỉnh và cấp xã"}${catalogPreview.field ? ` · ${esc(catalogPreview.field)}` : ""}${catalogPreview.query ? ` · Từ khóa “${esc(catalogPreview.query)}”` : ""}</span></div>` : "";
    const periodNotice = state.demo === "normal" && state.screen !== "operations" && loaded && period().provisional ? `<div class="period-notice" role="status"><strong>Số liệu tạm thời</strong><span>Kỳ báo cáo này chưa kết thúc. Kết quả có thể thay đổi khi hệ thống nguồn cập nhật dữ liệu.</span></div>` : "";
    const staleNotice = loaded?.delivery?.stale ? `<div class="period-notice stale" role="status"><strong>Chưa cập nhật được</strong><span>${esc(loaded.delivery.message ?? "Đang sử dụng bản dữ liệu hoàn chỉnh gần nhất.")}</span></div>` : "";
    const completedNotice = completionMessage ? `<div class="period-notice success" role="status"><strong>Thống kê hoàn tất</strong><span>${esc(completionMessage)}</span><button class="btn small" data-action="dismiss-completion">Đóng</button></div>` : "";
    searchableSelects.forEach(control => control.destroy());
    searchableSelects = [];
    const timingNotice = loaded?.delivery?.detailsAvailable === false ? `<div class="period-notice" role="status"><strong>Chỉ có điểm tổng hợp tỉnh</strong><span>Kỳ này có đủ điểm 6 nhóm để so sánh tỉnh; chưa có chỉ tiêu thành phần hoặc điểm sở/ngành, xã/phường. Chọn kỳ không tạo yêu cầu thu thập.</span></div>` : state.demo === "normal" && loaded?.delivery?.result === "national-summary" && loaded.delivery.capturedAt !== loaded.delivery.detailsCapturedAt ? `<div class="period-notice" role="status"><strong>Hai thời điểm cập nhật</strong><span>Điểm tỉnh: ${esc(dateTime(loaded.delivery.capturedAt))}. Chi tiết chỉ tiêu và điểm cơ quan trực thuộc: ${esc(dateTime(loaded.delivery.detailsCapturedAt))}. Số liệu thành phần có thể chưa khớp điểm tỉnh mới nhất.</span></div>` : "";
    root.innerHTML = `<div class="app-shell">${nav()}<div class="workspace">${context()}<main class="content">${formalityNotice}${completedNotice}${staleNotice}${periodNotice}${timingNotice}${content}</main></div>${state.modal === "brief" ? briefModal() : state.modal === "export" ? exportModal() : ""}</div>`;
    bind();
}
function initSearchableSelects() {
    const settings = [
        { selector: "#province-select", placeholder: "Nhập tên tỉnh/thành phố…" },
        { selector: "#unit-select", placeholder: "Nhập tên cơ quan, đơn vị…" },
    ];
    for (const item of settings) {
        const element = document.querySelector(item.selector);
        if (!element)
            continue;
        const control = new TomSelect(element, {
            create: false,
            maxItems: 1,
            maxOptions: null,
            placeholder: item.placeholder,
            searchField: ["text"],
            sortField: [{ field: "$score", direction: "desc" }, { field: "$order", direction: "asc" }],
            render: { no_results: () => '<div class="no-results">Không tìm thấy kết quả phù hợp</div>' },
        });
        const showSearchHint = () => { control.control_input.placeholder = item.placeholder; };
        control.on("focus", () => { window.requestAnimationFrame(showSearchHint); });
        control.on("dropdown_open", showSearchHint);
        control.on("blur", () => { control.control_input.placeholder = ""; });
        searchableSelects.push(control);
    }
}
function unavailable(kind) {
    if (kind === "ready")
        return catalogReady();
    if (kind === "loading")
        return `${title("Đang tải dữ liệu", "Đang chuẩn hóa dữ liệu theo đơn vị và kỳ báo cáo.")}<div class="boot-grid"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>`;
    if (kind === "queued")
        return `${title("Đang chờ cập nhật dữ liệu", "Yêu cầu đã được lưu trong hàng đợi an toàn.")}<div class="empty-state"><h2>Đang chuẩn bị dữ liệu cho lựa chọn này</h2><p>${esc(pendingMessage || "Hệ thống đang xử lý tuần tự và sẽ tự hiển thị khi snapshot hoàn chỉnh được lưu vào PostgreSQL.")}</p><button class="btn" data-action="retry-selection">Kiểm tra lại</button></div>`;
    if (kind === "blocked")
        return `${title("Đang chờ kết nối nguồn", "Yêu cầu đã được lưu an toàn và sẽ giữ nguyên cho tới khi kết nối DVCQG được quản trị viên kiểm tra.")}<div class="empty-state"><p>${esc(pendingMessage || "Hệ thống không tự vượt WAF hoặc gửi thêm request.")}</p><div class="empty-actions"><button class="btn" data-action="retry-selection">Kiểm tra lại</button><button class="btn primary" data-nav="operations">Xem trạng thái vận hành</button></div></div>`;
    if (kind === "error")
        return `${title("Dữ liệu không hợp lệ", "Hệ thống chưa thể tổng hợp báo cáo ở thời điểm này.")}<div class="empty-state"><h2>Không thể hiển thị báo cáo</h2><p>Vui lòng thử lại hoặc liên hệ cán bộ quản trị dữ liệu. Các trường chưa có dữ liệu không được tính là 0.</p><button class="btn primary" data-state="normal">Thử lại</button></div>`;
    if (kind === "empty")
        return `${title("Không có dữ liệu", "Đơn vị hoặc kỳ được chọn không có bản ghi hợp lệ.")}<div class="empty-state"><h2>Không có dữ liệu cho lựa chọn hiện tại</h2><p>Hãy đổi kỳ báo cáo hoặc phạm vi TTHC. Giá trị null được giữ nguyên và không tham gia xếp hạng.</p><button class="btn" data-state="normal">Về dữ liệu thật</button></div>`;
    return `${title("Chưa đủ dữ liệu lịch sử", "Hệ thống chưa có chuỗi kỳ đồng nhất để so sánh.")}<div class="empty-state"><h2>Cần tối thiểu hai kỳ cùng loại</h2><p>Hiện có Tháng 8/2026, Quý III/2026 và Năm 2026. Ba kỳ này khác độ dài nên không được ghép thành một xu hướng.</p><button class="btn" data-state="normal">Quay lại báo cáo</button></div>`;
}
function render() {
    if (state.screen === "operations")
        return shell(operations());
    if (state.demo !== "normal")
        return shell(unavailable(state.demo));
    if (snapshot().delivery?.detailsAvailable === false && state.unitId !== data.province.id)
        return shell(`<section class="panel"><div class="empty-state"><h2>Chưa có điểm cơ quan trong kỳ này</h2><p>Hiện chỉ có điểm tổng hợp tỉnh. Chọn UBND tỉnh để xem và so sánh 6 nhóm, hoặc chọn kỳ khác có dữ liệu cơ quan.</p></div></section>`);
    const content = state.screen === "overview" ? overview()
        : state.screen === "time" ? time()
            : state.screen === "peers" ? peers()
                : state.screen === "procedure" ? procedure()
                    : state.screen === "suggestions" ? suggestions()
                        : quality();
    shell(content);
}
function overview() {
    const view = unit();
    const previousPeriod = previousPeriodFor();
    const previousView = previousPeriod ? buildUnitView(data, previousPeriod.id, state.scope, state.unitId) : null;
    const currentRank = rankFor(view, state.periodId, null);
    const previousRank = previousView && previousPeriod ? rankFor(previousView, previousPeriod.id, null) : null;
    const scoreChange = previousView?.totalScore !== null && previousView?.totalScore !== undefined && view.totalScore !== null ? view.totalScore - previousView.totalScore : null;
    const rankChange = currentRank && previousRank ? previousRank.rank - currentRank.rank : null;
    const suggestions = buildSuggestions(view);
    const priority = suggestions.filter((item) => item.severity === "critical" || item.severity === "warning").slice(0, 3);
    const strengths = suggestions.filter((item) => item.severity === "positive").slice(0, 3);
    const captures = snapshot().datasets.map((item) => item.capture.capturedAt).filter(Boolean).sort();
    return `${title("Tổng quan cơ quan, đơn vị", `Toàn cảnh điểm số, vị thế và việc cần ưu tiên của ${view.name}.`, "Mặc định hiển thị năm hiện tại và tất cả thủ tục hành chính.")}
  <section class="kpi-strip" aria-label="Tóm tắt điều hành"><article class="kpi"><div class="kpi-label">Tổng điểm <span class="badge ${level(view.ratio)[1]}">${level(view.ratio)[0]}</span></div><div class="kpi-value large num">${n(view.totalScore)} <small>/ ${n(view.totalMaximum)}</small></div><div class="progress"><i style="width:${Math.min(view.ratio ?? 0, 100)}%"></i></div></article><article class="kpi"><div class="kpi-label">Vị thế trong nhóm cùng cấp</div><div class="kpi-value num">${currentRank ? `${currentRank.rank}/${currentRank.total}` : "Chưa xếp hạng"}</div><div class="kpi-sub">${currentRank ? `Phân vị P${Math.round(currentRank.percentile)}${currentRank.tiedCount > 1 ? ` · ${currentRank.tiedCount} đơn vị đồng hạng` : ""}` : "Chưa có đủ đơn vị cùng cấp trong kỳ"}</div></article><article class="kpi"><div class="kpi-label">So với kỳ trước</div><div class="kpi-value num ${scoreChange === null ? "" : scoreChange >= 0 ? "positive" : "negative"}">${scoreChange === null ? "Chưa đủ kỳ" : `${scoreChange >= 0 ? "+" : ""}${n(scoreChange)} điểm`}</div><div class="kpi-sub">${previousPeriod ? `${esc(previousPeriod.label)}${rankChange === null ? "" : ` · thứ hạng ${rankChange > 0 ? "tăng" : rankChange < 0 ? "giảm" : "không đổi"} ${Math.abs(rankChange)}`}` : "Cần thêm kỳ cùng loại để tính biến động"}</div></article><article class="kpi"><div class="kpi-label">Trạng thái dữ liệu <span class="badge ${view.groups.every(group => group.score.value !== null) ? "good" : "warn"}">${view.groups.every(group => group.score.value !== null) ? "Đủ điểm nhóm" : "Chưa đủ điểm"}</span></div><div class="kpi-value">${view.groups.filter(group => group.score.value !== null).length}/${view.groups.length} nhóm</div><div class="kpi-sub">Điểm: ${esc(dateTime(state.unitId === data.province.id ? snapshot().delivery?.capturedAt ?? captures.at(-1) : snapshot().delivery?.detailsCapturedAt ?? captures.at(-1)))} · Chi tiết: ${esc(dateTime(snapshot().delivery?.detailsAvailable === false ? null : snapshot().delivery?.detailsCapturedAt ?? captures.at(-1)))}</div></article></section>
  <section class="group-grid">${view.groups.map(groupPanel).join("")}</section>
  ${overviewGroupDetail(view)}
  <section class="split"><article class="panel"><div class="panel-head"><div><h2>Vấn đề cần ưu tiên</h2><p>Dựa trên khoảng cách với trung vị và cảnh báo dữ liệu</p></div><span class="badge warn">${priority.length} phát hiện</span></div><div class="panel-body ticket-list">${priority.length ? priority.map((item) => miniTicket(item, false)).join("") : `<div class="empty-state"><h2>Chưa có cảnh báo ưu tiên</h2></div>`}</div></article><article class="panel"><div class="panel-head"><div><h2>Kết quả tốt cần duy trì</h2><p>Nhóm thuộc phân vị cao hoặc gần bão hòa điểm</p></div><span class="badge good">Điểm mạnh</span></div><div class="panel-body ticket-list">${strengths.length ? strengths.map((item) => miniTicket(item, true)).join("") : `<div class="empty-state"><h2>Chưa xác định điểm mạnh nổi bật</h2><p>Kết quả hiện tại chưa nằm trong nhóm dẫn đầu.</p></div>`}</div></article></section>`;
}
function groupPanel(group) {
    const score = scoreValue(group), maximum = group.maximum, ratio = score !== null && maximum ? score / maximum * 100 : null;
    const peer = rankFor(group, state.periodId, group.id);
    const marker = peer && maximum ? Math.max(0, Math.min(100, peer.median / maximum * 100)) : 0;
    const stateLabel = level(ratio);
    const gap = peer?.gapToMedian ?? null;
    return `<button class="group-panel ${state.selectedGroup === group.id ? "selected" : ""}" data-group-detail="${group.id}" aria-pressed="${state.selectedGroup === group.id}"><div class="group-top"><h3>${esc(group.label)}</h3><span class="badge ${stateLabel[1]}">${stateLabel[0]}</span></div><div class="score-row"><div><span class="score-main num">${n(score)}</span> <span class="score-max">/ ${n(maximum)}</span></div><span class="rank">${peer ? `Hạng ${peer.rank}/${peer.total}` : "Chưa xếp hạng"}</span></div><div class="bullet" title="Thanh xanh: điểm đơn vị; vạch đen: trung vị nhóm cùng cấp"><i class="bullet-fill" style="width:${Math.min(ratio ?? 0, 100)}%"></i><b class="bullet-marker" style="left:${marker}%"></b></div><div class="bullet-labels"><span>0</span><span>Trung vị ${n(peer?.median)}</span><span>${n(maximum)}</span></div><div class="gap-note ${(gap ?? 0) >= 0 ? "positive" : "negative"}">${gap === null ? "Chưa có chuẩn so sánh" : `${gap >= 0 ? "+" : ""}${n(gap)}đ ${gap >= 0 ? "trên" : "dưới"} trung vị`}</div></button>`;
}
function totalPeerComparison(view) {
    const selected = data.units.find(item => item.departmentId === state.unitId);
    const isProvince = selected?.departmentLevel === "PROVINCE_TOTAL";
    const rows = isProvince
        ? (provinceBenchmarks[benchmarkCacheKey(state.periodId)] ?? []).flatMap(item => item.totalScore === null ? [] : [{ id: item.rootDepartmentId, name: item.provinceName, score: item.totalScore }])
        : allUnitTotals(snapshot(), selected?.departmentLevel ?? "COMMUNE").map(item => ({ id: item.id, name: item.name, score: item.score }));
    rows.sort((left, right) => right.score - left.score || alphabet.compare(left.name, right.name));
    const currentIndex = rows.findIndex(item => item.id === state.unitId);
    const nearby = currentIndex < 0 ? [] : rows.slice(Math.max(0, currentIndex - 2), Math.min(rows.length, currentIndex + 3));
    const current = rows[currentIndex];
    const stats = current && rows.length > 1 ? peerStats(rows.map(item => item.score), current.score) : null;
    const heading = isProvince ? "So sánh tổng điểm với tỉnh/thành phố khác" : "So sánh tổng điểm với đơn vị cùng cấp";
    if (!stats)
        return `<aside class="comparison-card"><h3>${heading}</h3><div class="empty-state"><h2>Chưa đủ dữ liệu so sánh</h2><p>Cần tối thiểu hai đơn vị cùng cấp, cùng kỳ và cùng phạm vi.</p></div></aside>`;
    return `<aside class="comparison-card"><h3>${heading}</h3><div class="comparison-kpi"><span>Thứ hạng tổng 6 nhóm</span><strong class="num">${stats.rank}/${stats.total}</strong></div><div class="comparison-kpi"><span>Trung vị tổng điểm</span><strong class="num">${n(stats.median)}</strong></div><div class="nearby-list">${nearby.map(item => `<div class="peer-row ${item.id === state.unitId ? "mine" : ""}"><span>${esc(item.name)}</span><b class="num">${n(item.score)}</b><small>Hạng ${1 + rows.filter(other => other.score > item.score + .005).length}</small></div>`).join("")}</div></aside>`;
}
function groupComparisonSummary(view) {
    const previousPeriod = previousPeriodFor();
    const previousView = previousPeriod ? buildUnitView(data, previousPeriod.id, state.scope, state.unitId) : null;
    const rows = view.groups.map(group => {
        const previousGroup = previousView?.groups.find(item => item.id === group.id) ?? null;
        const currentScore = scoreValue(group);
        const previousScore = previousGroup ? scoreValue(previousGroup) : null;
        const scoreChange = currentScore !== null && previousScore !== null ? currentScore - previousScore : null;
        const currentRank = rankFor(group, state.periodId, group.id);
        const previousRank = previousGroup && previousPeriod ? rankFor(previousGroup, previousPeriod.id, group.id) : null;
        const rankChange = currentRank && previousRank ? previousRank.rank - currentRank.rank : null;
        const rankChangeText = rankChange === null ? "—" : rankChange > 0 ? `↑ ${rankChange} bậc` : rankChange < 0 ? `↓ ${Math.abs(rankChange)} bậc` : "Không đổi";
        return `<tr class="selectable-row" data-group-detail="${group.id}"><td><button class="row-link">${esc(group.label)}</button></td><td class="num"><strong>${n(currentScore)}</strong> / ${n(group.maximum)}</td><td class="num">${previousPeriod ? n(previousScore) : "—"}</td><td class="num ${scoreChange === null ? "" : scoreChange >= 0 ? "positive" : "negative"}">${scoreChange === null ? "—" : `${scoreChange >= 0 ? "+" : ""}${n(scoreChange)}`}</td><td class="num ${rankChange === null ? "" : rankChange >= 0 ? "positive" : "negative"}">${rankChangeText}</td></tr>`;
    }).join("");
    return `<section class="panel group-comparison" id="group-detail"><div class="panel-head"><div><p class="eyebrow">Tổng hợp 6 nhóm chỉ tiêu</p><h2>Điểm số và biến động theo kỳ</h2><p>${esc(view.name)} · ${esc(period().label)}${previousPeriod ? ` so với ${esc(previousPeriod.label)}` : " · chưa có kỳ trước cùng loại"}</p></div></div><div class="detail-columns"><div class="detail-metrics-card"><h3>Điểm 6 nhóm chỉ tiêu</h3><div class="table-wrap"><table class="summary-table"><thead><tr><th>Tên nhóm chỉ tiêu</th><th>Điểm số</th><th>Điểm kỳ trước</th><th>Tăng/giảm so với kỳ trước</th><th>Tăng/giảm thứ hạng</th></tr></thead><tbody>${rows}</tbody></table></div></div>${totalPeerComparison(view)}</div></section>`;
}
function onlineAnalysis(entity) {
    const analysis = analyzeOnlineScore(entity);
    if (!analysis)
        return null;
    const rows = analysis.components.map(component => `<tr class="selectable-row ${state.selectedMetric === `online:${component.id}` ? "selected" : ""}" data-metric-detail="online:${component.id}"><td><button class="row-link">${esc(component.name)}</button><small class="metric-note">Mục tiêu tính đủ điểm: ${pct(component.targetPercent)}</small></td><td class="num">${int(component.numerator)}</td><td class="num">${int(component.denominator)}</td><td class="num">${pct(component.ratio)}</td><td class="num">${n(component.score)}</td><td class="num">${n(component.maxScore)}</td><td class="num lost">${n(component.missingScore)}</td></tr>`);
    const status = analysis.matchesApi === true ? "Khớp với điểm Cổng công bố" : analysis.matchesApi === false ? "Có chênh lệch, cần rà soát công thức" : "Chưa có điểm API để đối chiếu";
    const tone = analysis.matchesApi === false ? "warn" : "";
    const difference = analysis.difference === null ? "" : ` · chênh ${n(Math.abs(analysis.difference), 3)} điểm`;
    const notice = `<div class="banner ${tone} formula-banner"><span>∑</span><div><strong>${esc(analysis.profileLabel)} · ${esc(status)}</strong><p>Điểm tính lại ${n(analysis.calculatedScore)} / 12${difference}. Điểm Cổng DVCQG vẫn là giá trị chính thức; cấu hình công thức có thể cập nhật mà không thay đổi dữ liệu nguồn đã lưu.</p></div></div>`;
    const catalog = `<div class="indicator-catalog"><h4>6 chỉ tiêu nghiệp vụ của nhóm</h4>${ONLINE_SCORING_PROFILE.declaredIndicators.map(item => `<div class="indicator-item"><span class="badge neutral">${esc(item.scope)}</span><div><strong>${esc(item.name)}</strong><small>${esc(item.dataStatus)}</small></div></div>`).join("")}</div>`;
    return { rows, notice: notice + catalog, catalog };
}
function progressDetail(entity) {
    const analysis = analyzeProgressScore(entity);
    if (!analysis)
        return null;
    const progressPercent = (value) => value === null ? "—" : `${n(value)}%`;
    const status = analysis.matchesApi === true ? "Khớp với điểm Cổng công bố" : analysis.matchesApi === false ? "Có chênh lệch, cần rà soát dữ liệu" : "Chưa đủ dữ liệu để đối chiếu";
    const tone = analysis.matchesApi === false ? "warn" : "";
    const difference = analysis.difference === null ? "" : ` · chênh ${n(Math.abs(analysis.difference), 3)} điểm`;
    const formula = analysis.onTimeRatio === null || analysis.calculatedScore === null
        ? "Không tính tỷ lệ và điểm khi tổng hồ sơ tiếp nhận bằng 0."
        : `${int(analysis.totalOnTime)} / ${int(analysis.totalReceived)} = ${progressPercent(analysis.onTimeRatio)}; ${progressPercent(analysis.onTimeRatio)} × ${n(analysis.maxScore)} = ${n(analysis.calculatedScore)} điểm.`;
    const averageDays = analysis.averageProcessingDays === null ? "N/A" : `${n(analysis.averageProcessingDays)} ngày`;
    return `<h3>Kết quả và công thức tính điểm</h3><div class="progress-kpis"><article><span>Tổng hồ sơ tiếp nhận</span><strong class="num">${int(analysis.totalReceived)}</strong><small>hồ sơ</small></article><article><span>Giải quyết đúng hạn</span><strong class="num positive">${int(analysis.totalOnTime)}</strong><small>${progressPercent(analysis.onTimeRatio)}</small></article><article><span>Hồ sơ quá hạn</span><strong class="num negative">${int(analysis.totalOverdue)}</strong><small>${progressPercent(analysis.overdueRatio)}${analysis.overdueDerived ? " · suy ra từ tổng và đúng hạn" : ""}</small></article><article><span>Giải quyết trung bình</span><strong class="num">${averageDays}</strong><small>hai chữ số thập phân</small></article></div><div class="banner ${tone} formula-banner progress-formula"><span>∑</span><div><strong>${esc(analysis.profileLabel)} · ${esc(status)}</strong><p>${esc(formula)}${difference} Điểm ghi nhận được tính bằng tỷ lệ đúng hạn nhân điểm tối đa.</p></div></div><div class="table-wrap"><table class="metric-table progress-table"><thead><tr><th>Nội dung</th><th>Số lượng</th><th>Tỷ lệ</th><th>Vai trò</th></tr></thead><tbody><tr><td>Tổng hồ sơ tiếp nhận</td><td class="num">${int(analysis.totalReceived)} hồ sơ</td><td class="num">—</td><td>Mẫu số tính tỷ lệ đúng hạn</td></tr><tr class="selectable-row ${state.selectedMetric === "progress:on-time" ? "selected" : ""}" data-metric-detail="progress:on-time"><td><button class="row-link">Hồ sơ giải quyết đúng hạn</button></td><td class="num">${int(analysis.totalOnTime)} hồ sơ</td><td class="num positive">${progressPercent(analysis.onTimeRatio)}</td><td>Tử số tính tỷ lệ và điểm</td></tr><tr><td>Hồ sơ quá hạn</td><td class="num">${int(analysis.totalOverdue)} hồ sơ</td><td class="num negative">${progressPercent(analysis.overdueRatio)}</td><td>Chỉ số theo dõi bổ sung</td></tr><tr><td>Số ngày giải quyết trung bình</td><td class="num">${averageDays}</td><td class="num">—</td><td>Chỉ số thời gian tham khảo</td></tr></tbody><tfoot><tr><td>Điểm ghi nhận</td><td colspan="2" class="num">${n(analysis.calculatedScore)} / ${n(analysis.maxScore)} điểm</td><td class="lost">Còn ${n(analysis.missingScore)} điểm chưa đạt</td></tr></tfoot></table></div>`;
}
function metricPoint(entity, key) {
    if (key === "progress:on-time") {
        const result = analyzeProgressScore(entity);
        return result?.calculatedScore === null || result?.calculatedScore === undefined ? null : { label: "Tỷ lệ hồ sơ giải quyết đúng hạn", score: result.calculatedScore, maximum: result.maxScore };
    }
    if (key.startsWith("online:")) {
        const component = analyzeOnlineScore(entity)?.components.find(item => `online:${item.id}` === key);
        return component ? { label: component.name, score: component.score, maximum: component.maxScore } : null;
    }
    const metric = entity.metrics.find(item => `raw:${item.code}` === key);
    return metric?.apiScore === null || metric?.apiScore === undefined ? null : { label: metric.name, score: metric.apiScore, maximum: metric.apiMaxScore };
}
function benchmarkMetricPoint(group, key) {
    if (key === "progress:on-time") {
        const result = analyzeProgressScore({ parameters: group.parameters, apiScore: group.score, apiMaxScore: group.maximum });
        return result?.calculatedScore === null || result?.calculatedScore === undefined ? null : { label: "Tỷ lệ hồ sơ giải quyết đúng hạn", score: result.calculatedScore, maximum: result.maxScore };
    }
    if (key.startsWith("online:")) {
        const result = analyzeOnlineScore({ parameters: group.parameters, apiScore: group.score });
        const component = result?.components.find(item => `online:${item.id}` === key);
        return component ? { label: component.name, score: component.score, maximum: component.maxScore } : null;
    }
    const metric = group.metrics[key.replace(/^raw:/, "")];
    return metric?.score === null || metric?.score === undefined ? null : { label: metric.name, score: metric.score, maximum: metric.maximum };
}
function metricPeerComparison(group, key) {
    const selected = data.units.find(item => item.departmentId === state.unitId);
    const isProvince = selected?.departmentLevel === "PROVINCE_TOTAL";
    const currentPoint = group.entity ? metricPoint(group.entity, key) : null;
    const rows = isProvince
        ? (provinceBenchmarks[benchmarkCacheKey(state.periodId)] ?? []).flatMap(item => { const source = item.groups[group.id]; const point = source ? benchmarkMetricPoint(source, key) : null; return point ? [{ id: item.rootDepartmentId, name: item.provinceName, score: point.score }] : []; })
        : (group.dataset?.children ?? []).filter(item => item.departmentLevel === selected?.departmentLevel).flatMap(item => { const point = metricPoint(item, key); return point ? [{ id: item.departmentId, name: item.departmentName, score: point.score }] : []; });
    rows.sort((left, right) => right.score - left.score || alphabet.compare(left.name, right.name));
    const currentIndex = rows.findIndex(item => item.id === state.unitId);
    const nearby = currentIndex < 0 ? [] : rows.slice(Math.max(0, currentIndex - 2), Math.min(rows.length, currentIndex + 3));
    const stats = currentPoint && rows.length > 1 ? peerStats(rows.map(item => item.score), currentPoint.score) : null;
    const heading = isProvince ? "So sánh chỉ tiêu với tỉnh/thành phố khác" : "So sánh chỉ tiêu với đơn vị cùng cấp";
    if (!stats)
        return `<aside class="comparison-card"><h3>${heading}</h3><strong>${esc(currentPoint?.label ?? "Chỉ tiêu được chọn")}</strong><div class="empty-state"><h2>Chưa đủ dữ liệu so sánh</h2></div></aside>`;
    return `<aside class="comparison-card metric-comparison"><h3>${heading}</h3><strong>${esc(currentPoint?.label)}</strong><div class="comparison-kpi"><span>Điểm chỉ tiêu</span><strong class="num">${n(currentPoint?.score)}${currentPoint?.maximum === null ? "" : ` / ${n(currentPoint?.maximum)}`}</strong></div><div class="comparison-kpi"><span>Thứ hạng</span><strong class="num">${stats.rank}/${stats.total}</strong></div><div class="nearby-list">${nearby.map(item => `<div class="peer-row ${item.id === state.unitId ? "mine" : ""}"><span>${esc(item.name)}</span><b class="num">${n(item.score)}</b><small>Hạng ${1 + rows.filter(other => other.score > item.score + .005).length}</small></div>`).join("")}</div></aside>`;
}
function groupPeerComparison(group) {
    if (state.selectedMetric)
        return metricPeerComparison(group, state.selectedMetric);
    const selected = data.units.find(item => item.departmentId === state.unitId);
    if (selected?.departmentLevel === "PROVINCE_TOTAL") {
        const rows = (provinceBenchmarks[benchmarkCacheKey(state.periodId)] ?? []).flatMap(item => {
            const score = item.groups[group.id]?.score;
            return score === null || score === undefined ? [] : [{ id: item.rootDepartmentId, name: item.provinceName, score }];
        }).sort((left, right) => right.score - left.score || alphabet.compare(left.name, right.name));
        const currentIndex = rows.findIndex(item => item.id === state.unitId);
        const nearby = currentIndex < 0 ? [] : rows.slice(Math.max(0, currentIndex - 2), Math.min(rows.length, currentIndex + 3));
        const stats = benchmarkRank(state.periodId, group.id);
        if (!stats)
            return `<aside class="comparison-card"><h3>So với tỉnh/thành phố khác</h3><div class="empty-state"><h2>Chưa đủ dữ liệu liên tỉnh</h2><p>Cần có ít nhất hai tỉnh/thành phố cùng kỳ và cùng phạm vi để so sánh.</p></div></aside>`;
        return `<aside class="comparison-card"><h3>So với tỉnh/thành phố khác</h3><div class="comparison-kpi"><span>Thứ hạng</span><strong class="num">${stats.rank}/${stats.total}</strong></div><div class="comparison-kpi"><span>Trung vị các tỉnh</span><strong class="num">${n(stats.median)}</strong></div><div class="nearby-list">${nearby.map(item => `<div class="peer-row ${item.id === state.unitId ? "mine" : ""}"><span>${esc(item.name)}</span><b class="num">${n(item.score)}</b><small>Hạng ${1 + rows.filter(other => other.score > item.score + .005).length}</small></div>`).join("")}</div></aside>`;
    }
    const comparable = (group.dataset?.children ?? []).filter(item => item.departmentLevel === selected?.departmentLevel && item.apiScore !== null).sort((a, b) => (b.apiScore ?? 0) - (a.apiScore ?? 0));
    const position = comparable.findIndex(item => item.departmentId === state.unitId);
    const nearby = position < 0 ? [] : comparable.slice(Math.max(0, position - 2), Math.min(comparable.length, position + 3));
    return `<aside class="comparison-card"><h3>So với đơn vị cùng cấp</h3>${group.peer ? `<div class="comparison-kpi"><span>Trung vị</span><strong class="num">${n(group.peer.median)}</strong></div><div class="comparison-kpi"><span>Chênh lệch</span><strong class="num ${(group.peer.gapToMedian) >= 0 ? "positive" : "negative"}">${group.peer.gapToMedian >= 0 ? "+" : ""}${n(group.peer.gapToMedian)}</strong></div><div class="nearby-list">${nearby.map(item => `<div class="peer-row ${item.departmentId === state.unitId ? "mine" : ""}"><span>${esc(item.departmentName)}</span><b class="num">${n(item.apiScore)}</b><small>Hạng ${1 + comparable.filter(other => (other.apiScore ?? 0) > (item.apiScore ?? 0) + .005).length}</small></div>`).join("")}</div>` : `<div class="empty-state"><h2>Chưa đủ đơn vị cùng cấp</h2></div>`}</aside>`;
}
function overviewGroupDetail(view) {
    if (state.selectedGroup === null)
        return groupComparisonSummary(view);
    const group = view.groups.find(item => item.id === state.selectedGroup);
    if (!group)
        return groupComparisonSummary(view);
    const entity = group.entity;
    if (!entity)
        return `<section class="panel group-detail"><div class="panel-head"><div><h2>Chi tiết ${esc(group.label)}</h2><p>Chưa có số liệu chi tiết cho lựa chọn hiện tại.</p></div></div></section>`;
    const calculated = group.id === "provide-online-tree" ? onlineAnalysis(entity) : null;
    const progress = group.id === "dvc-progress-tree" ? progressDetail(entity) : null;
    const metricRows = entity.metrics.map(m => m.apiScore === null ? `<tr><td>${esc(m.name)}</td><td class="num">${int(m.numerator)}</td><td class="num">${int(m.denominator)}</td><td class="num">${pct(m.ratio)}</td><td class="num">${n(m.apiScore)}</td><td class="num">${n(m.apiMaxScore)}</td><td class="num lost">N/A</td></tr>` : `<tr class="selectable-row ${state.selectedMetric === `raw:${m.code}` ? "selected" : ""}" data-metric-detail="raw:${esc(m.code)}"><td><button class="row-link">${esc(m.name)}</button></td><td class="num">${int(m.numerator)}</td><td class="num">${int(m.denominator)}</td><td class="num">${pct(m.ratio)}</td><td class="num">${n(m.apiScore)}</td><td class="num">${n(m.apiMaxScore)}</td><td class="num lost">${m.apiMaxScore !== null ? n(Math.max(0, m.apiMaxScore - m.apiScore)) : "N/A"}</td></tr>`);
    const valueRows = calculated ? calculated.rows : Object.entries(entity.parameters).filter(([, value]) => value !== null).map(([key, value]) => `<tr><td>${esc(parameterLabels[key] ?? "Số liệu nghiệp vụ thành phần")}</td><td colspan="3" class="num">${esc(typeof value === "number" ? int(value) : value)}</td><td colspan="3">Được sử dụng để theo dõi và phân tích kết quả</td></tr>`);
    const rows = [...metricRows, ...valueRows];
    const lost = entity.apiScore !== null && entity.apiMaxScore !== null ? Math.max(0, entity.apiMaxScore - entity.apiScore) : null;
    const comparison = groupPeerComparison(group);
    const detailRank = rankFor(group, state.periodId, group.id);
    const emptyDetailMessage = group.id === "provide-online-tree" && data.units.find(item => item.departmentId === state.unitId)?.departmentLevel !== "PROVINCE_TOTAL"
        ? "Nguồn hiện chỉ công bố điểm và tỷ lệ của cơ quan trực thuộc; số liệu thành phần Dịch vụ công trực tuyến mới có ở cấp tỉnh."
        : "Nhóm này chưa có số liệu thành phần để hiển thị.";
    const heading = `<div class="panel-head"><div><p class="eyebrow">Chi tiết nhóm chỉ tiêu</p><h2>${esc(group.label)}</h2><p>${esc(view.name)} · ${esc(period().label)}</p></div><div class="detail-summary"><button class="text-button" data-action="close-group-detail">← Xem lại 6 nhóm</button>${state.selectedMetric ? `<button class="text-button" data-action="clear-metric-detail">← So sánh cả nhóm</button>` : ""}<strong class="num">${n(entity.apiScore)} / ${n(entity.apiMaxScore)}</strong><span>${detailRank ? `Hạng ${detailRank.rank}/${detailRank.total}` : "Chưa xếp hạng"}</span></div></div>`;
    if (progress)
        return `<section class="panel group-detail" id="group-detail">${heading}<div class="detail-columns"><div class="detail-metrics-card progress-detail">${progress}</div>${comparison}</div></section>`;
    return `<section class="panel group-detail" id="group-detail">${heading}<div class="detail-columns"><div class="detail-metrics-card"><h3>Kết quả các chỉ tiêu thành phần</h3>${calculated?.notice ?? ""}<div class="table-wrap"><table class="metric-table"><thead><tr><th>Chỉ tiêu hoặc số liệu nghiệp vụ</th><th>Số lượng đạt</th><th>Tổng số</th><th>Tỷ lệ</th><th>Điểm ghi nhận</th><th>Điểm tối đa</th><th>Điểm chưa đạt</th></tr></thead><tbody>${rows.length ? rows.join("") : `<tr><td colspan="7">${esc(emptyDetailMessage)}</td></tr>`}</tbody><tfoot><tr><td colspan="4">Tổng điểm</td><td class="num">${n(entity.apiScore)}</td><td class="num">${n(entity.apiMaxScore)}</td><td class="num lost">${n(lost)}</td></tr></tfoot></table></div></div>${comparison}</div></section>`;
}
function miniTicket(item, good) { return `<div class="mini-ticket"><i class="ticket-dot ${good ? "good" : ""}"></i><div><strong>${esc(item.finding)}</strong><p>${esc(item.evidence)} ${esc(item.action)}</p></div></div>`; }
function time() {
    const samples = data.periods.filter(p => p.type === period().type && Boolean(data.snapshots[snapshotKey(p.id, state.scope, data.formality.id)]))
        .sort((a, b) => periodOrder(a) - periodOrder(b)).map(p => ({ p, v: buildUnitView(data, p.id, state.scope, state.unitId) }));
    const rows = samples.map(({ p, v }) => {
        const previous = previousAvailablePeriod(data, p.id, state.scope);
        const prior = previous ? buildUnitView(data, previous.id, state.scope, state.unitId) : null;
        const delta = v.totalScore !== null && prior?.totalScore !== null && prior?.totalScore !== undefined ? v.totalScore - prior.totalScore : null;
        const rank = rankFor(v, p.id, null);
        return `<tr><td>${esc(p.label)}${p.provisional ? ' <span class="badge warn">Tạm thời</span>' : ""}</td><td class="num">${n(v.totalScore)}</td><td class="num">${n(prior?.totalScore)}</td><td class="num">${delta === null ? "—" : (delta >= 0 ? "+" : "") + n(delta)}</td><td class="num">${rank ? rank.rank + "/" + rank.total : "—"}</td>${v.groups.map(group => `<td class="num">${n(group.score.value)}</td>`).join("")}</tr>`;
    }).join("");
    return `${title("So sánh theo thời gian", "Điểm các kỳ cùng loại và biến động so với kỳ liền trước.", "Kỳ đang diễn ra được đánh dấu tạm thời; không ghép tháng, quý và năm.")}<section class="panel"><div class="panel-head"><div><h2>Chuỗi điểm cùng loại kỳ</h2><p>Thiếu kỳ liền trước thì không tính biến động. Thứ hạng chỉ hiển thị khi đã đọc dữ liệu so sánh của kỳ đó.</p></div></div><div class="table-wrap"><table><thead><tr><th>Kỳ</th><th>Tổng điểm</th><th>Điểm kỳ trước</th><th>Tăng/giảm điểm</th><th>Thứ hạng</th>${data.groupOrder.map(group => `<th>${esc(data.groupLabels[group])}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div></section>`;
}
function dimensionValues() {
    const snap = snapshot();
    const selected = data.units.find(x => x.departmentId === state.unitId);
    const level = selected?.departmentLevel;
    if (level === "PROVINCE_TOTAL")
        return { label: "Tổng điểm", current: unit().totalScore ?? 0, maximum: unit().totalMaximum ?? 100, rows: [] };
    const totals = allUnitTotals(snap, level ?? "COMMUNE");
    if (state.peerDimension === "total") {
        const current = totals.find(x => x.id === state.unitId);
        return { label: "Tổng điểm", current: current?.score ?? 0, maximum: current?.maximum ?? 100, rows: totals };
    }
    const dataset = snap.datasets.find(d => d.group === state.peerDimension);
    const rows = (dataset?.children ?? []).filter(e => e.departmentLevel === level && e.apiScore !== null && e.apiMaxScore !== null).map(e => ({ id: e.departmentId, name: e.departmentName, score: e.apiScore, maximum: e.apiMaxScore, ratio: e.apiMaxScore ? e.apiScore / e.apiMaxScore * 100 : 0, volume: 0 }));
    const current = rows.find(x => x.id === state.unitId);
    return { label: data.groupLabels[state.peerDimension], current: current?.score ?? 0, maximum: current?.maximum ?? 0, rows };
}
function peers() {
    const dim = dimensionValues();
    const stats = peerStats(dim.rows.map(x => x.score), dim.current);
    const ordered = [...dim.rows].sort((a, b) => b.score - a.score || a.name.localeCompare(b.name, "vi"));
    const neighbors = state.peerDimension === "total" ? immediatePeers(snapshot(), state.unitId) : ordered.slice(Math.max(0, ordered.findIndex(x => x.id === state.unitId) - 3), ordered.findIndex(x => x.id === state.unitId) + 4);
    const similar = similarVolumePeers(snapshot(), state.unitId);
    const min = Math.min(...dim.rows.map(x => x.score)), max = Math.max(...dim.rows.map(x => x.score));
    const pos = (v) => max === min ? 50 : 3 + (v - min) / (max - min) * 94;
    if (!dim.rows.length)
        return `${title("So sánh trong tỉnh", `Vị thế của ${unit().name}.`, "Kết quả chung toàn tỉnh không xếp hạng cùng các cơ quan trực thuộc.")}<div class="empty-state"><h2>Hãy chọn một Sở, ngành hoặc xã/phường</h2><p>Hệ thống sẽ so sánh đơn vị được chọn với các đơn vị cùng cấp có dữ liệu hợp lệ.</p></div>`;
    return `${title("So sánh trong tỉnh", `Vị thế của ${unit().name} trong nhóm cơ quan, đơn vị cùng cấp.`, "Chỉ các đơn vị cùng cấp và có dữ liệu hợp lệ mới tham gia xếp hạng.")}<div class="table-toolbar"><div class="segmented"><button data-dimension="total" class="${state.peerDimension === "total" ? "active" : ""}">Tổng điểm</button>${data.groupOrder.map(g => `<button data-dimension="${g}" class="${state.peerDimension === g ? "active" : ""}">${esc(data.groupLabels[g])}</button>`).join("")}</div></div>${stats ? `<section class="panel"><div class="panel-head"><div><h2>${esc(dim.label)}</h2><p>Phân phối điểm của các đơn vị cùng cấp</p></div><span class="badge info">${rankText({ peer: stats })}</span></div><div class="panel-body"><div class="stats-row"><div class="stat"><span>Điểm đơn vị</span><strong class="num">${n(dim.current)}</strong></div><div class="stat"><span>Trung bình</span><strong class="num">${n(stats.mean)}</strong></div><div class="stat"><span>Trung vị</span><strong class="num">${n(stats.median)}</strong></div><div class="stat"><span>Ngưỡng 25% dẫn đầu</span><strong class="num">${n(stats.p75)}</strong></div><div class="stat"><span>Phân vị</span><strong class="num">P${Math.round(stats.percentile)}</strong></div></div><div class="distribution"><div class="distribution-line"></div><i class="tick" style="left:${pos(stats.median)}%"><label>Trung vị ${n(stats.median)}</label></i><i class="tick" style="left:${pos(stats.p75)}%"><label>Nhóm dẫn đầu ${n(stats.p75)}</label></i><i class="tick current" style="left:${pos(dim.current)}%"><label>Đơn vị đang xem ${n(dim.current)}</label></i></div></div></section>` : ""}<section class="peer-grid"><article class="panel"><div class="panel-head"><div><h2>Đơn vị liền kề trong xếp hạng</h2><p>Ba đơn vị ngay trên và dưới đơn vị đang xem</p></div></div><div class="panel-body">${neighbors.map((x) => peerRow(x.name, x.score, x.id === state.unitId, x.score - dim.current)).join("")}</div></article><article class="panel"><div class="panel-head"><div><h2>Quy mô hồ sơ tương đồng</h2><p>So sánh theo tổng số hồ sơ tiếp nhận</p></div></div><div class="panel-body">${similar.map(x => peerRow(x.name, x.score, false, x.volume)).join("")}</div></article></section><section class="panel" style="margin-top:12px"><div class="panel-head"><div><h2>Bảng xếp hạng</h2><p>Ghim đơn vị đang xem; tìm nhanh theo tên</p></div><input id="peer-search" type="search" value="${esc(state.search)}" placeholder="Tìm cơ quan, đơn vị…" /></div><div class="table-wrap"><table><thead><tr><th>Hạng</th><th>Đơn vị</th><th>Điểm</th><th>Mức đạt</th><th>Chênh lệch</th></tr></thead><tbody>${ordered.filter(x => x.id === state.unitId || x.name.toLocaleLowerCase("vi").includes(state.search.toLocaleLowerCase("vi"))).slice(0, 60).map(x => `<tr class="${x.id === state.unitId ? "mine" : ""}"><td class="num">${1 + ordered.filter(y => y.score > x.score + .005).length}</td><td>${esc(x.name)}${x.id === state.unitId ? ` <span class="badge info">Đơn vị đang xem</span>` : ""}</td><td class="num">${n(x.score)}</td><td><span class="bar-cell"><i style="--w:${Math.min(x.ratio, 100)}%"></i>${pct(x.ratio)}</span></td><td class="num">${x.score - dim.current >= 0 ? "+" : ""}${n(x.score - dim.current)}</td></tr>`).join("")}</tbody></table></div></section>`;
}
function peerRow(name, score, mine, extra) { return `<div class="peer-row ${mine ? "mine" : ""}"><span>${esc(name)}${mine ? " · Đơn vị đang xem" : ""}</span><b class="num">${n(score)}</b><span class="num muted">${extra >= 0 ? "+" : ""}${n(extra)}</span></div>`; }
function procedure() {
    const view = unit("formality");
    const all = unit("all");
    const sections = view.groups.map(group => group.id === "handling-satisfaction" ? `<div class="banner warn"><span>!</span><div><strong>${esc(group.label)} · Không có số liệu riêng theo từng TTHC</strong><p>Mức độ hài lòng hiện được tổng hợp chung theo cơ quan, đơn vị, chưa tách riêng cho thủ tục ${esc(data.formality.code)}.</p></div></div>` : diagnostic(group)).join("");
    return `${title("Phân tích theo thủ tục hành chính", `${data.formality.code} · ${data.formality.name}`, "Kết quả chi tiết của thủ tục hành chính được chọn.")}<div class="banner"><span>i</span><div><strong>Phạm vi phân tích</strong><p>Năm nhóm chỉ tiêu có số liệu chi tiết theo thủ tục hành chính. Mức độ hài lòng hiện chỉ được tổng hợp chung theo cơ quan, đơn vị.</p></div></div><section class="kpi-strip"><article class="kpi"><div class="kpi-label">Điểm 5 nhóm có số liệu</div><div class="kpi-value large num">${n(view.totalScore)} / ${n(view.totalMaximum)}</div><div class="kpi-sub">Không cộng Mức độ hài lòng vào phạm vi TTHC</div></article><article class="kpi"><div class="kpi-label">Điểm tất cả TTHC</div><div class="kpi-value num">${n(all.totalScore)}</div><div class="kpi-sub">Mốc tham chiếu của cơ quan, đơn vị</div></article><article class="kpi"><div class="kpi-label">Thủ tục đang xem</div><div class="kpi-value">${esc(data.formality.code)}</div><div class="kpi-sub">${esc(data.formality.name)}</div></article><article class="kpi"><div class="kpi-label">So sánh theo thời gian</div><div class="kpi-value">Chưa đủ kỳ</div><div class="kpi-sub">Cần thêm các kỳ cùng loại để xác định xu hướng</div></article></section>${sections}`;
}
function diagnostic(group) {
    const entity = group.entity;
    if (!entity)
        return `<div class="empty-state"><h2>${esc(group.label)}</h2><p>Nguồn không trả dữ liệu cho TTHC này.</p></div>`;
    const progress = group.id === "dvc-progress-tree" ? progressDetail(entity) : null;
    if (progress)
        return `<section class="panel" style="margin-bottom:12px"><div class="panel-head"><div><h2>${esc(group.label)}</h2><p>Tính điểm từ tỷ lệ hồ sơ giải quyết đúng hạn; tỷ lệ quá hạn và thời gian xử lý được hiển thị để phân tích.</p></div><span class="badge good">${n(entity.apiScore)} / ${n(entity.apiMaxScore)}</span></div><div class="panel-body progress-detail">${progress}</div></section>`;
    const calculated = group.id === "provide-online-tree" ? onlineAnalysis(entity) : null;
    const rows = calculated ? calculated.rows.join("") : entity.metrics.length ? entity.metrics.map(m => `<tr><td>${esc(m.name)}</td><td class="num">${int(m.numerator)}</td><td class="num">${int(m.denominator)}</td><td class="num">${pct(m.ratio)}</td><td class="num">${n(m.apiScore)}</td><td class="num">${n(m.apiMaxScore)}</td><td class="num lost">${m.apiScore !== null && m.apiMaxScore !== null ? n(Math.max(0, m.apiMaxScore - m.apiScore)) : "N/A"}</td></tr>`).join("") : Object.entries(entity.parameters).map(([key, value]) => `<tr><td>${esc(parameterLabels[key] ?? "Chỉ số nghiệp vụ")}</td><td colspan="3" class="num">${esc(typeof value === "number" ? int(value) : value)}</td><td class="num">—</td><td class="num">—</td><td class="num">—</td></tr>`).join("");
    const lost = entity.apiScore !== null && entity.apiMaxScore !== null ? Math.max(0, entity.apiMaxScore - entity.apiScore) : null;
    const description = calculated ? "Ba chỉ tiêu thành phần được tính lại để giải thích điểm; điểm Cổng công bố vẫn là giá trị chính thức." : group.dataset?.schemaKind === "parameters" ? "Hiển thị các số liệu nghiệp vụ thành phần; chưa có đủ dữ liệu để phân rã điểm." : "Kết quả chi tiết theo chỉ tiêu thành phần.";
    return `<section class="panel" style="margin-bottom:12px"><div class="panel-head"><div><h2>${esc(group.label)}</h2><p>${description}</p></div><span class="badge ${calculated ? "good" : "info"}">${n(entity.apiScore)} / ${n(entity.apiMaxScore)}</span></div>${calculated?.notice ?? ""}<div class="table-wrap"><table class="metric-table"><thead><tr><th>Chỉ tiêu hoặc số liệu nghiệp vụ</th><th>Số lượng đạt</th><th>Tổng số</th><th>Tỷ lệ</th><th>Điểm ghi nhận</th><th>Điểm tối đa</th><th>Điểm chưa đạt</th></tr></thead><tbody>${rows || `<tr><td colspan="7">Chưa có số liệu chi tiết.</td></tr>`}</tbody><tfoot><tr><td colspan="4">Tổng điểm</td><td class="num">${n(entity.apiScore)}</td><td class="num">${n(entity.apiMaxScore)}</td><td class="num lost">${n(lost)}</td></tr></tfoot></table></div></section>`;
}
function suggestions() {
    const list = buildSuggestions(unit());
    const urgent = list.filter(x => x.severity === "critical" || x.severity === "warning");
    const positive = list.filter(x => x.severity === "positive");
    return `${title("Gợi ý cải thiện", "Nhận diện nội dung cần ưu tiên từ kết quả hiện tại và mặt bằng các đơn vị cùng cấp.", "Không ước lượng điểm khi cách tính chi tiết chưa được xác nhận.")}<div class="banner"><span>i</span><div><strong>Phạm vi gợi ý hiện tại</strong><p>Hệ thống xem xét khoảng cách với trung vị, mức điểm gần tối đa, điểm mạnh và trường hợp có quá ít hồ sơ. Các nhận định cần nhiều kỳ sẽ hiển thị khi có thêm dữ liệu lịch sử.</p></div></div><div class="tabs"><button class="active">Tất cả (${list.length})</button><button>Cần xử lý (${urgent.length})</button><button>Điểm mạnh (${positive.length})</button></div><section class="ticket-grid">${list.map(ticket).join("")}</section><section class="panel" style="margin-top:12px"><div class="panel-head"><div><h2>Ma trận mức ảnh hưởng và nguồn lực thực hiện</h2><p>Hỗ trợ lựa chọn việc ưu tiên; mức nguồn lực cần được cán bộ nghiệp vụ xác nhận.</p></div><span class="badge warn">Cần xác nhận nghiệp vụ</span></div><div class="panel-body matrix"><div class="quadrant"><strong>Ảnh hưởng cao · Nguồn lực thấp</strong><p>Ưu tiên xử lý trước</p>${urgent.slice(0, 2).map(x => `<span class="matrix-chip">${esc(data.groupLabels[x.groupId] ?? x.finding)}</span>`).join("")}</div><div class="quadrant"><strong>Ảnh hưởng cao · Nguồn lực cao</strong><p>Lập kế hoạch theo kỳ</p><span class="matrix-chip">Cần cán bộ nghiệp vụ đánh giá</span></div><div class="quadrant"><strong>Ảnh hưởng thấp · Nguồn lực thấp</strong><p>Duy trì thường xuyên</p>${positive.slice(0, 2).map(x => `<span class="matrix-chip">${esc(data.groupLabels[x.groupId] ?? x.finding)}</span>`).join("")}</div><div class="quadrant"><strong>Ảnh hưởng thấp · Nguồn lực cao</strong><p>Theo dõi, chưa ưu tiên</p><span class="matrix-chip">Chờ xác nhận cách tính</span></div></div></section>`;
}
function ticket(item) { const labels = { gap: "Thấp hơn mặt bằng", saturation: "Gần điểm tối đa", quality: "Cần kiểm tra số liệu", formula: "Chờ xác nhận cách tính", strength: "Kết quả tốt" }; return `<article class="ticket ${item.severity}"><div class="ticket-head"><span class="badge ${item.severity === "critical" ? "bad" : item.severity === "warning" ? "warn" : item.severity === "positive" ? "good" : "info"}">${labels[item.category]}</span><h3>${esc(item.finding)}</h3></div><div class="ticket-body"><div class="ticket-part"><span>Căn cứ</span><p>${esc(item.evidence)}</p></div><div class="ticket-part"><span>Mức ảnh hưởng</span><p>${esc(item.impact)}</p></div><div class="ticket-part"><span>Hành động đề xuất</span><p>${esc(item.action)}</p></div><div class="ticket-part"><span>Lưu ý khi sử dụng</span><p>${item.category === "formula" ? "Chưa thể thử thay đổi điểm khi cách tính chưa được xác nhận." : "Nhận định áp dụng cho kỳ và phạm vi đang chọn."}</p></div></div><div class="ticket-actions"><span class="badge neutral">Độ tin cậy: ${esc(item.confidence)}</span><button class="btn small" data-nav="${item.deepLink}">Xem chi tiết →</button></div></article>`; }
function quality() {
    const snap = snapshot();
    const entities = snap.datasets.map(d => d.root.departmentId === state.unitId ? d.root : d.children.find(e => e.departmentId === state.unitId)).filter((e) => Boolean(e));
    const metrics = entities.flatMap(e => e.metrics);
    const values = entities.flatMap(e => Object.values(e.parameters));
    const missing = metrics.filter(m => m.apiScore === null || m.ratio === null).length;
    const zeros = metrics.filter(m => m.apiScore === 0 || m.ratio === 0).length + values.filter(v => v === 0).length;
    const small = metrics.filter(m => m.denominator !== null && m.denominator > 0 && m.denominator <= 3).length;
    const coverageRows = snap.datasets.map(dataset => {
        const entity = dataset.root.departmentId === state.unitId ? dataset.root : dataset.children.find(item => item.departmentId === state.unitId);
        const businessParameters = entity ? Object.entries(entity.parameters).filter(([key, value]) => key !== "scoreDelta" && value !== null) : [];
        const hasDetail = Boolean(entity && (entity.metrics.length > 0 || businessParameters.length > 0));
        const status = hasDetail ? "Có chi tiết" : entity?.apiScore !== null && entity?.apiScore !== undefined ? "Chỉ có điểm" : "Thiếu dữ liệu";
        const tone = hasDetail ? "good" : status === "Chỉ có điểm" ? "warn" : "bad";
        return `<tr><td>${esc(dataset.label)}</td><td class="num">${esc(dateTime(dataset.capture.capturedAt))}</td><td><span class="badge ${tone}">${status}</span></td></tr>`;
    }).join("");
    return `${title("Độ tin cậy của số liệu", "Theo dõi mức độ đầy đủ và các lưu ý khi sử dụng kết quả.", "Các trường không có số liệu, bằng 0 và không áp dụng được phân biệt rõ.")}<section class="quality-grid"><article class="quality-card"><h3>Mức độ đầy đủ điểm số</h3><strong class="num">${snap.status.loadedGroups.length}/${snap.status.requiredGroups.length}</strong><p>${snap.status.state === "complete" ? "Đã có điểm của đủ sáu nhóm; mức chi tiết phụ thuộc dữ liệu nguồn." : "Một số nhóm chỉ tiêu chưa có điểm số."}</p></article><article class="quality-card"><h3>Chưa có số liệu</h3><strong class="num">${missing}</strong><p>Các trường này hiển thị “Không có dữ liệu” và không được tính là 0.</p></article><article class="quality-card"><h3>Giá trị bằng 0</h3><strong class="num">${zeros}</strong><p>Đây là giá trị đã ghi nhận bằng 0, khác với trường hợp chưa có dữ liệu.</p></article><article class="quality-card"><h3>Số lượng hồ sơ quá ít</h3><strong class="num">${small}</strong><p>Một hồ sơ có thể làm tỷ lệ thay đổi mạnh; cần thận trọng khi đánh giá.</p></article><article class="quality-card"><h3>Không áp dụng ở cấp xã</h3><strong>Đang rà soát</strong><p>Tiêu chí không áp dụng được hưởng điểm tối đa theo quy định; nhãn sẽ hiển thị sau khi đối chiếu chính xác từng chỉ tiêu.</p></article><article class="quality-card"><h3>Giới hạn hiện tại</h3><strong class="num">2</strong><p>DVCTT chưa có tham số thành phần cho cơ quan trực thuộc; công thức Thanh toán trực tuyến chưa được xác minh.</p></article></section><section class="panel" style="margin-top:12px"><div class="panel-head"><div><h2>Thời điểm cập nhật theo nhóm chỉ tiêu</h2><p>Phân biệt rõ dữ liệu có chi tiết với trường hợp nguồn chỉ công bố điểm.</p></div><span class="badge good">Đã cập nhật</span></div><div class="table-wrap"><table><thead><tr><th>Nhóm chỉ tiêu</th><th>Thời điểm cập nhật</th><th>Mức dữ liệu</th></tr></thead><tbody>${coverageRows}</tbody></table></div></section>`;
}
function catalogReady() {
    const selected = catalogPreview.items.find(item => item.id === catalogPreview.selectedId) ?? null;
    const rows = catalogPreview.items.map(item => `<label class="catalog-row ${item.id === catalogPreview.selectedId && catalogPreview.mode === "single" ? "selected" : ""}">${catalogPreview.mode === "single" ? `<input type="radio" name="catalog-formality" value="${esc(item.id)}" ${item.id === catalogPreview.selectedId ? "checked" : ""}>` : `<span class="catalog-batch-mark">✓</span>`}<span><strong>${esc(item.code)}</strong><small>${esc(item.name)}</small><em>${esc(item.field || "Chưa phân loại")} · ${item.executionLevels.includes("ward") ? "Cấp xã" : item.executionLevels.includes("province") ? "Cấp tỉnh" : ""}</em></span><span class="badge ${item.available ? "good" : "neutral"}">${item.available ? "Đã có dữ liệu" : "Cần thống kê"}</span></label>`).join("");
    const first = catalogPreview.selected ? catalogPreview.offset + 1 : 0;
    const last = Math.min(catalogPreview.offset + catalogPreview.items.length, catalogPreview.selected);
    const canSubmit = catalogPreview.mode === "filtered" ? catalogPreview.selected > 0 : Boolean(selected);
    const selectionText = catalogPreview.mode === "filtered" ? `<strong>${int(catalogPreview.selected)} TTHC sau lọc</strong><span>${int(catalogPreview.available)} đã có · ${int(catalogPreview.missing)} cần thu thập tuần tự</span>` : selected ? `<strong>${esc(selected.code)}</strong><span>${esc(selected.name)}</span>` : `<strong>Chưa chọn TTHC</strong><span>Chọn một dòng trong danh sách để tiếp tục.</span>`;
    return `${title("Chọn thủ tục hành chính", "Lọc và xem trước phạm vi trước khi tạo yêu cầu thống kê.", "Thay đổi bộ lọc không tạo job và không gọi DVCQG.")}<section class="panel catalog-panel"><div class="catalog-mode"><button class="${catalogPreview.mode === "single" ? "active" : ""}" data-catalog-mode="single">Một TTHC</button><button class="${catalogPreview.mode === "filtered" ? "active" : ""}" data-catalog-mode="filtered">Toàn bộ kết quả sau lọc</button></div><div class="catalog-filters"><label class="field"><span>Cấp thực hiện</span><select id="catalog-level"><option value="">Cấp tỉnh và cấp xã</option><option value="province" ${catalogPreview.level === "province" ? "selected" : ""}>Cấp tỉnh</option><option value="ward" ${catalogPreview.level === "ward" ? "selected" : ""}>Cấp xã</option></select></label><label class="field"><span>Lĩnh vực</span><select id="catalog-field"><option value="">Tất cả lĩnh vực</option>${catalogPreview.fields.map(field => `<option value="${esc(field)}" ${field === catalogPreview.field ? "selected" : ""}>${esc(field)}</option>`).join("")}</select></label><label class="field catalog-search"><span>Tìm mã hoặc tên TTHC</span><input id="catalog-query" type="search" value="${esc(catalogPreview.query)}" placeholder="Ví dụ: 2.000815 hoặc từ khóa"></label></div><div class="catalog-summary"><article><span>Kết quả sau lọc</span><strong>${int(catalogPreview.selected)}</strong></article><article><span>Đã có trong PostgreSQL</span><strong>${int(catalogPreview.available)}</strong></article><article><span>Cần thống kê mới</span><strong>${int(catalogPreview.missing)}</strong></article></div>${catalogPreview.loading ? `<div class="empty-state"><h2>Đang đọc danh mục…</h2></div>` : catalogPreview.error ? `<div class="banner warn"><span>!</span><div><strong>Chưa đọc được danh mục</strong><p>${esc(catalogPreview.error)}</p></div></div>` : `<div class="catalog-list">${rows || `<div class="empty-state"><h2>Không tìm thấy TTHC phù hợp</h2><p>Hãy thay đổi cấp thực hiện, lĩnh vực hoặc từ khóa.</p></div>`}</div><div class="catalog-pagination"><span>Hiển thị ${int(first)}–${int(last)} trong ${int(catalogPreview.selected)} TTHC</span><div><button class="btn small" data-action="catalog-prev" ${catalogPreview.offset === 0 ? "disabled" : ""}>Trang trước</button><button class="btn small" data-action="catalog-next" ${last >= catalogPreview.selected ? "disabled" : ""}>Trang sau</button></div></div>`}<div class="catalog-submit"><div>${selectionText}</div><button class="btn primary" data-action="submit-statistics" ${canSubmit ? "" : "disabled"}>${catalogPreview.mode === "filtered" ? "Thống kê toàn bộ" : "Thống kê"}</button></div></section>`;
}
function operationPeriod(job) {
    const selected = job.request.period;
    if (!selected)
        return "Không xác định";
    if (selected.type === "month")
        return `Tháng ${selected.month}/${selected.year}`;
    if (selected.type === "quarter")
        return `Quý ${selected.quarter}/${selected.year}`;
    return `Năm ${selected.year ?? "—"}`;
}
function operationScope(job) {
    if (job.request.scope !== "formality")
        return "Tất cả TTHC";
    return `${job.formalityCode ?? "Chưa rõ mã"} · ${job.formalityName ?? "Chưa có tên thủ tục"}`;
}
function operations() {
    const queued = operationData.jobs.filter(job => job.state === "queued").length;
    const running = operationData.jobs.filter(job => job.state === "running").length;
    const stopped = operationData.jobs.filter(job => job.state === "failed" || job.state === "halted").length;
    const circuitOpen = operationData.circuitState === "open";
    const rows = operationData.jobs.map(job => {
        const scope = operationScope(job);
        return `<tr><td class="num">${esc(job.id.slice(0, 8))}</td><td>${esc(operationPeriod(job))}</td><td>${esc(job.provinceName ?? "Chưa xác định")}</td><td class="operation-scope" title="${esc(scope)}">${esc(scope)}</td><td><span class="badge ${job.state === "succeeded" ? "good" : job.state === "running" ? "info" : job.state === "queued" ? "warn" : "bad"}">${esc(job.state)}</span></td><td class="num">${job.attempts}</td><td>${esc(dateTime(job.createdAt))}</td></tr>`;
    }).join("");
    const batchRows = operationData.batches.map(batch => {
        const finished = batch.availableItems + batch.completedItems;
        return `<tr><td class="num">${esc(batch.id.slice(0, 8))}</td><td>${esc(batch.periodType)} ${batch.periodValue ?? ""}/${batch.year}</td><td class="num">${int(finished)}/${int(batch.totalItems)}</td><td class="num">${int(batch.availableItems)}</td><td><span class="badge ${batch.state === "succeeded" ? "good" : batch.state === "running" ? "info" : batch.state === "queued" ? "warn" : "bad"}">${esc(batch.state)}</span></td><td>${batch.state === "failed" || batch.state === "halted" ? `<button class="btn small" data-resume-batch="${esc(batch.id)}">Tiếp tục</button>` : "—"}</td></tr>`;
    }).join("");
    const provinceBatchRows = operationData.provinceBatches.map(batch => {
        const finished = batch.availableItems + batch.completedItems;
        const failed = batch.failedItems ? ` · ${int(batch.failedItems)} lỗi` : "";
        return `<tr><td class="num">${esc(batch.id.slice(0, 8))}</td><td>${esc(batchPeriod(batch))}</td><td class="num">${int(finished)}/${int(batch.totalItems)}</td><td class="num">${int(batch.availableItems)}</td><td class="num">${int(batch.completedItems)}${failed}</td><td><span class="badge ${batch.state === "succeeded" ? "good" : batch.state === "running" ? "info" : batch.state === "queued" ? "warn" : "bad"}">${esc(batch.state)}</span></td></tr>`;
    }).join("");
    const content = operationData.loading
        ? `<div class="boot-grid"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>`
        : operationData.error
            ? `<div class="banner bad"><span>!</span><div><strong>Không đọc được trạng thái vận hành</strong><p>${esc(operationData.error)}</p></div></div>`
            : `<section class="quality-grid"><article class="quality-card"><h3>Kết nối DVCQG</h3><strong class="status-text ${circuitOpen ? "negative" : "positive"}">${circuitOpen ? "Đang tạm dừng" : "Sẵn sàng"}</strong><p>${circuitOpen ? "Worker không được phép gọi nguồn cho tới khi quản trị viên kiểm tra và chủ động mở lại." : "Circuit đang đóng; worker chỉ xử lý tuần tự theo giới hạn an toàn."}</p></article><article class="quality-card"><h3>Job đang chờ</h3><strong class="num">${queued}</strong><p>${running} đang chạy · ${stopped} đã dừng hoặc thất bại.</p></article><article class="quality-card"><h3>Snapshot hoàn chỉnh</h3><strong class="num">${operationData.snapshotCount}</strong><p>Cập nhật gần nhất: ${esc(dateTime(operationData.latestSnapshotAt))}.</p></article></section><div class="banner ${circuitOpen ? "warn" : ""}" style="margin-top:12px"><span>${circuitOpen ? "!" : "i"}</span><div><strong>${circuitOpen ? "Cần kiểm tra kết nối trước khi chạy" : "Luồng thu thập đang được bảo vệ"}</strong><p>${esc(operationData.circuitReason ?? (circuitOpen ? "Chưa có mô tả nguyên nhân." : "Không có cảnh báo circuit."))} Mỗi batch chỉ mở một job con tại một thời điểm.</p></div></div><section class="panel" style="margin-top:12px"><div class="panel-head"><div><h2>Làm mới chi tiết 34 tỉnh/thành phố</h2><p>Kỳ đang diễn ra được làm mới luân phiên; snapshot đã có dưới 72 giờ sẽ được dùng lại.</p></div><button class="btn small" data-action="refresh-operations">Làm mới</button></div><div class="table-wrap"><table><thead><tr><th>Mã batch</th><th>Kỳ</th><th>Tiến độ</th><th>Dùng lại</th><th>Thu thập mới</th><th>Trạng thái</th></tr></thead><tbody>${provinceBatchRows || `<tr><td colspan="6">Chưa có batch làm mới chi tiết. Lịch đầu tiên chạy lúc 02:15.</td></tr>`}</tbody></table></div></section><section class="panel" style="margin-top:12px"><div class="panel-head"><div><h2>Batch thống kê theo TTHC</h2><p>Tiến độ được lưu trong PostgreSQL và có thể tiếp tục từ checkpoint.</p></div></div><div class="table-wrap"><table><thead><tr><th>Mã batch</th><th>Kỳ</th><th>Tiến độ</th><th>Dùng lại</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${batchRows || `<tr><td colspan="6">Chưa có batch thống kê nào.</td></tr>`}</tbody></table></div></section><section class="panel" style="margin-top:12px"><div class="panel-head"><div><h2>Hàng đợi cập nhật dữ liệu</h2><p>Các yêu cầu được chống trùng và xử lý ngoài vòng đời request giao diện.</p></div></div><div class="table-wrap"><table><thead><tr><th>Mã job</th><th>Kỳ</th><th>Tỉnh/Thành phố</th><th>Phạm vi</th><th>Trạng thái</th><th>Số lần thử</th><th>Thời điểm tạo</th></tr></thead><tbody>${rows || `<tr><td colspan="7">Chưa có yêu cầu nào trong hàng đợi.</td></tr>`}</tbody></table></div></section>`;
    return `${title("Trạng thái vận hành", "Theo dõi kết nối nguồn, snapshot và hàng đợi cập nhật dữ liệu.", "Chỉ hiển thị thông tin an toàn; việc mở circuit vẫn thực hiện theo runbook quản trị.")}${content}`;
}
async function loadOperations() {
    operationData.loading = true;
    operationData.error = null;
    render();
    try {
        const [statusResponse, jobsResponse, batchesResponse, provinceBatchesResponse] = await Promise.all([fetch("/api/v1/system-status"), fetch("/api/v1/collection-jobs?limit=50"), fetch("/api/v1/formality-batches?limit=20"), fetch("/api/v1/province-batches?limit=20")]);
        if (!statusResponse.ok || !jobsResponse.ok || !batchesResponse.ok || !provinceBatchesResponse.ok)
            throw new Error(`HTTP ${statusResponse.status}/${jobsResponse.status}/${batchesResponse.status}/${provinceBatchesResponse.status}`);
        const status = await statusResponse.json();
        operationData = { loading: false, error: null, circuitState: status.circuitState, circuitReason: status.circuitReason, snapshotCount: status.snapshotCount, latestSnapshotAt: status.latestSnapshotAt, jobs: await jobsResponse.json(), batches: await batchesResponse.json(), provinceBatches: await provinceBatchesResponse.json() };
    }
    catch (error) {
        operationData.loading = false;
        operationData.error = error instanceof Error ? error.message : String(error);
    }
    render();
}
function briefModal() {
    const report = leadershipReport(), loading = benchmarkLoading.has(benchmarkCacheKey(state.periodId));
    const point = (value) => value === null ? "—" : n(value);
    return `<div class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Báo cáo xếp hạng cho lãnh đạo"><div class="modal ranking-modal"><div class="modal-top no-print"><strong>Báo cáo lãnh đạo · Xếp hạng cùng cấp</strong><div><button class="btn small primary" data-action="leadership-excel" ${report.rows.length ? "" : "disabled"}>Tải Excel</button> <button class="btn small" data-action="print" ${report.rows.length ? "" : "disabled"}>In / PDF</button> <button class="btn small" data-action="close-modal">Đóng</button></div></div><article class="ranking-report"><h1>XẾP HẠNG ĐÁNH GIÁ CHẤT LƯỢNG PHỤC VỤ</h1><p>${esc(report.period)} · ${esc(report.population)} · ${esc(report.scope)}</p><p class="muted">Cập nhật: ${esc(leadershipUpdatedLabel(report))}</p>${report.rows.length ? `<div class="ranking-scroll"><table class="leadership-table"><thead><tr><th>STT</th><th>${esc(report.nameHeader)}</th>${report.groupLabels.map((label, index) => `<th style="background:#${leadershipColors[index]}">${esc(label)}</th><th style="background:#${leadershipColors[index]}">Hạng</th>`).join("")}<th>Tổng điểm</th></tr></thead><tbody>${report.rows.map((row, index) => `<tr class="${row.id === report.selectedId ? "selected-agency" : ""}" ${row.id === report.selectedId ? 'aria-current="true"' : ""}><td>${index + 1}</td><td>${esc(row.name)}</td>${row.scores.map((score, i) => `<td>${point(score)}</td><td class="leadership-rank">${row.ranks[i] ?? "—"}</td>`).join("")}<td class="leadership-total">${point(row.total)}</td></tr>`).join("")}</tbody></table></div>` : `<p role="status">${loading ? "Đang đọc dữ liệu xếp hạng đã lưu…" : "Chưa có dữ liệu xếp hạng cho lựa chọn này. Không gửi yêu cầu lấy dữ liệu mới."}</p>`}<div class="ranking-notes"><p>Cơ quan đang chọn: <strong>${esc(report.selectedName)}</strong>. Dòng màu xanh là cơ quan đang chọn. STT là vị trí dòng theo tổng điểm giảm dần, không phải thứ hạng khi có đồng điểm.</p>${report.notes.map(note => `<p>${esc(note)}</p>`).join("")}</div></article></div></div>`;
}
const leadershipReport = () => {
    const report = buildLeadershipReport(data, state.periodId, state.scope, state.unitId, provinceBenchmarks[benchmarkCacheKey(state.periodId)] ?? []);
    if (state.demo !== "normal") {
        report.rows = [];
        report.capturedAt = [];
        report.notes = ["Có dữ liệu thật của lựa chọn hiện tại mới lập được báo cáo."];
    }
    return report;
};
async function openLeadershipReport() {
    state.modal = "brief";
    render();
    if (state.demo === "normal" && (state.unitId === data.province.id || data.units.find(item => item.departmentId === state.unitId)?.departmentLevel === "PROVINCE_TOTAL")) {
        // Re-read saved rankings on open so a later automatic refresh is reflected.
        if (!benchmarkLoading.has(benchmarkCacheKey(state.periodId)))
            delete provinceBenchmarks[benchmarkCacheKey(state.periodId)];
        const loading = loadProvinceBenchmarks();
        render();
        await loading;
    }
    if (state.modal === "brief")
        render();
}
async function downloadLeadershipExcel() {
    const report = leadershipReport();
    if (!report.rows.length)
        return;
    const workbook = buildLeadershipWorkbook(ExcelJS.Workbook, report);
    const snap = data.snapshots[snapshotKey(state.periodId, state.scope, data.formality.id)];
    const reportSnapshot = { ...(snap ?? { scope: state.scope, formalityId: null, status: { state: "incomplete", requiredGroups: [], loadedGroups: [], unsupportedGroups: [], missingGroups: [] }, provinceAggregatedScore: null, provinceAggregatedMaximum: null, scorePolicy: {}, datasets: [] }), delivery: { capturedAt: report.capturedAt.at(-1) ?? "" } };
    const filename = analysisExcelFilename(report.selectedName, reportSnapshot, "scores").replace("-tonghop-", "-tonghop-baocao-lanhdao-");
    const content = await workbook.xlsx.writeBuffer();
    const url = URL.createObjectURL(new Blob([new Uint8Array(content)], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function exportModal() {
    const selectedSnapshot = data.snapshots[snapshotKey(state.periodId, state.scope, data.formality.id)];
    const available = state.demo === "normal" && Boolean(selectedSnapshot) && (selectedSnapshot?.delivery?.detailsAvailable !== false || state.unitId === data.province.id);
    const detailsAvailable = available && selectedSnapshot?.delivery?.detailsAvailable !== false;
    return `<div class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Trung tâm xuất báo cáo"><div class="modal"><div class="modal-top"><strong>Xuất dữ liệu và báo cáo</strong><button class="btn small" data-action="close-modal">Đóng</button></div><div class="brief"><p class="eyebrow">${esc(data.units.find(item => item.departmentId === state.unitId)?.departmentName ?? data.province.name)} · ${esc(period().label)}</p><h1>Xuất dữ liệu đang xem</h1><p class="muted">Tệp Excel có tên chỉ tiêu tiếng Việt, định dạng số và bộ lọc. Giữ nguyên số 0, để trống giá trị chưa có; kèm kỳ và thời điểm cập nhật.${available ? "" : " Cần có dữ liệu của lựa chọn hiện tại trước khi xuất."}</p><div class="quality-grid" style="margin-top:18px"><article class="quality-card"><h3>Điểm 6 nhóm chỉ tiêu</h3><strong>Excel (.xlsx)</strong><p>Điểm nguồn, thứ hạng, trung vị và trạng thái dữ liệu của cơ quan đang chọn.</p><button class="btn small primary" data-export-excel="scores" ${available ? "" : "disabled"}>Tải Excel bảng điểm</button></article><article class="quality-card"><h3>Số liệu thành phần</h3><strong>Excel (.xlsx)</strong><p>Chỉ tiêu và số liệu nghiệp vụ của 6 nhóm, sử dụng tên tiếng Việt.</p><button class="btn small" data-export-excel="details" ${detailsAvailable ? "" : "disabled"}>Tải Excel chi tiết</button></article><article class="quality-card"><h3>Báo cáo lãnh đạo</h3><strong>Xếp hạng cùng cấp</strong><p>Điểm và hạng của 6 nhóm, tổng điểm; so sánh tỉnh, Sở ngành hoặc xã phường theo cơ quan đang chọn.</p><button class="btn small" data-action="brief">Xem báo cáo</button></article></div></div></div></div>`;
}
async function downloadAnalysisExcel(kind) {
    const snapshot = data.snapshots[snapshotKey(state.periodId, state.scope, data.formality.id)];
    if (!snapshot || state.demo !== "normal")
        return;
    if (snapshot.delivery?.detailsAvailable === false && (kind === "details" || state.unitId !== data.province.id))
        return;
    const view = unit();
    const rankedView = { ...view, peer: rankFor(view, state.periodId, null), groups: view.groups.map(group => ({ ...group, peer: rankFor(group, state.periodId, group.id) })) };
    const scopeLabel = state.scope === "all" ? "Tất cả TTHC" : `${data.formality.code} · ${data.formality.name}`;
    const workbook = buildAnalysisWorkbook(ExcelJS.Workbook, rankedView, snapshot, period(), data.province.name, scopeLabel, kind);
    const filename = analysisExcelFilename(view.name, snapshotForUnit(snapshot, view.id), kind);
    const content = await workbook.xlsx.writeBuffer();
    const bytes = new Uint8Array(content);
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function bind() {
    document.querySelector("[data-action=logout]")?.addEventListener("click", async () => {
        if (!signedInUser)
            return;
        const response = await fetch("/api/v1/auth/logout", { method: "POST", headers: { "X-QD766-CSRF": signedInUser.csrfToken } });
        if (response.ok)
            window.location.assign("/");
        else
            window.alert("Chưa đăng xuất được. Vui lòng thử lại.");
    });
    document.querySelectorAll("[data-nav]").forEach(el => el.addEventListener("click", () => { const destination = el.dataset.nav; state.screen = destination; if (destination === "operations") {
        state.demo = "normal";
        render();
        void loadOperations();
    }
    else if (data.snapshots[snapshotKey(state.periodId, state.scope, data.formality.id)]) {
        state.demo = "normal";
        render();
    }
    else if (state.scope === "formality" && !catalogPreview.selectedId) {
        state.demo = "ready";
        render();
        void loadCatalogPreview();
    }
    else {
        void loadSelection();
    } scrollTo(0, 0); }));
    document.querySelectorAll("[data-state]").forEach(el => el.addEventListener("click", () => { state.demo = el.dataset.state; render(); }));
    document.querySelectorAll("[data-dimension]").forEach(el => el.addEventListener("click", () => { state.peerDimension = el.dataset.dimension; render(); }));
    document.querySelectorAll("[data-group-detail]").forEach(el => el.addEventListener("click", () => { state.selectedGroup = el.dataset.groupDetail; state.selectedMetric = null; render(); document.querySelector("#group-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }); }));
    document.querySelectorAll("[data-metric-detail]").forEach(el => el.addEventListener("click", () => { state.selectedMetric = el.dataset.metricDetail ?? null; render(); document.querySelector(".comparison-card")?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }));
    document.querySelector("[data-action=clear-metric-detail]")?.addEventListener("click", () => { state.selectedMetric = null; render(); });
    document.querySelector("[data-action=close-group-detail]")?.addEventListener("click", () => { state.selectedGroup = null; state.selectedMetric = null; render(); document.querySelector("#group-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }); });
    document.querySelector("#province-select")?.addEventListener("change", e => { void switchProvince(e.target.value); });
    document.querySelector("#unit-select")?.addEventListener("change", e => { state.unitId = e.target.value; state.selectedGroup = null; state.selectedMetric = null; render(); });
    document.querySelector("#period-type")?.addEventListener("change", e => { const type = e.target.value; const currentYear = period().year; const matches = data.periods.filter(item => item.type === type && item.year === currentYear); const fallback = data.periods.filter(item => item.type === type); const match = matches.at(-1) ?? fallback.at(-1); if (match)
        void selectPeriod(match.id); });
    document.querySelector("#period-value")?.addEventListener("change", e => { void selectPeriod(e.target.value); });
    document.querySelector("#report-year")?.addEventListener("change", e => { const year = Number(e.target.value); const matches = data.periods.filter(item => item.type === period().type && item.year === year); const match = matches.at(-1); if (match)
        void selectPeriod(match.id); });
    document.querySelector("#scope-select")?.addEventListener("change", e => { completionMessage = ""; state.scope = e.target.value; state.selectedGroup = null; state.selectedMetric = null; if (state.scope === "formality") {
        state.demo = "ready";
        render();
        void loadCatalogPreview();
    }
    else {
        void loadSelection().then(() => loadProvinceBenchmarks());
    } });
    document.querySelector("#catalog-level")?.addEventListener("change", e => { catalogPreview.level = e.target.value; catalogPreview.selectedId = null; catalogPreview.offset = 0; void loadCatalogPreview(); });
    document.querySelector("#catalog-field")?.addEventListener("change", e => { catalogPreview.field = e.target.value; catalogPreview.selectedId = null; catalogPreview.offset = 0; void loadCatalogPreview(); });
    document.querySelector("#catalog-query")?.addEventListener("input", e => { catalogPreview.query = e.target.value; catalogPreview.selectedId = null; catalogPreview.offset = 0; window.clearTimeout(catalogSearchTimer); catalogSearchTimer = window.setTimeout(() => { void loadCatalogPreview(); }, 350); });
    document.querySelectorAll("input[name=catalog-formality]").forEach(el => el.addEventListener("change", () => { const item = catalogPreview.items.find(candidate => candidate.id === el.value); if (!item)
        return; catalogPreview.selectedId = item.id; data.formality = { id: item.id, code: item.code, name: item.name }; void loadSelection(); }));
    document.querySelectorAll("[data-catalog-mode]").forEach(el => el.addEventListener("click", () => { catalogPreview.mode = el.dataset.catalogMode; state.demo = "ready"; render(); }));
    document.querySelector("#peer-search")?.addEventListener("input", e => { state.search = e.target.value; render(); });
    document.querySelectorAll("[data-action=brief]").forEach(el => el.addEventListener("click", () => { void openLeadershipReport(); }));
    document.querySelector("[data-action=leadership-excel]")?.addEventListener("click", async (event) => {
        const button = event.currentTarget;
        button.disabled = true;
        try {
            await downloadLeadershipExcel();
        }
        catch (error) {
            console.error(error);
            window.alert("Không tạo được báo cáo Excel. Vui lòng thử lại.");
        }
        finally {
            button.disabled = false;
        }
    });
    document.querySelector("[data-action=export]")?.addEventListener("click", () => { state.modal = "export"; render(); });
    document.querySelectorAll("[data-export-excel]").forEach(el => el.addEventListener("click", async () => {
        el.disabled = true;
        const label = el.textContent;
        el.textContent = "Đang tạo Excel…";
        try {
            await downloadAnalysisExcel(el.dataset.exportExcel);
        }
        catch (error) {
            console.error(error);
            window.alert("Không tạo được tệp Excel. Anh/chị vui lòng tải lại trang và thử lại.");
        }
        finally {
            el.disabled = false;
            el.textContent = label;
        }
    }));
    document.querySelector("[data-action=close-modal]")?.addEventListener("click", () => { state.modal = "none"; render(); });
    document.querySelector("[data-action=print]")?.addEventListener("click", () => window.print());
    document.querySelector("[data-action=open-quality]")?.addEventListener("click", () => { state.screen = "quality"; render(); });
    document.querySelector("[data-action=retry-selection]")?.addEventListener("click", () => { if (pendingProvinceId)
        void switchProvince(pendingProvinceId);
    else
        void loadSelection(); });
    document.querySelectorAll("[data-action=submit-statistics]").forEach(el => el.addEventListener("click", () => { void submitStatistics(); }));
    document.querySelector("[data-action=dismiss-completion]")?.addEventListener("click", () => { completionMessage = ""; render(); });
    document.querySelector("[data-action=refresh-operations]")?.addEventListener("click", () => { void loadOperations(); });
    document.querySelectorAll("[data-resume-batch]").forEach(el => el.addEventListener("click", async () => { const id = el.dataset.resumeBatch; if (!id)
        return; el.setAttribute("disabled", ""); try {
        const response = await fetch(`/api/v1/formality-batches/${encodeURIComponent(id)}/resume`, { method: "POST" });
        if (!response.ok)
            throw new Error(`HTTP ${response.status}`);
        await loadOperations();
    }
    catch (error) {
        operationData.error = error instanceof Error ? error.message : String(error);
        render();
    } }));
    document.querySelector("[data-action=catalog-prev]")?.addEventListener("click", () => { catalogPreview.offset = Math.max(0, catalogPreview.offset - 100); void loadCatalogPreview(); });
    document.querySelector("[data-action=catalog-next]")?.addEventListener("click", () => { catalogPreview.offset += 100; void loadCatalogPreview(); });
    initSearchableSelects();
}
function mergeUnits(snapshot) {
    const known = new Set(data.units.map(item => item.departmentId));
    for (const dataset of snapshot.datasets) {
        for (const entity of [dataset.root, ...dataset.children]) {
            if (known.has(entity.departmentId))
                continue;
            data.units.push({ departmentId: entity.departmentId, departmentName: entity.departmentName, departmentType: entity.departmentType, departmentLevel: entity.departmentLevel });
            known.add(entity.departmentId);
        }
    }
}
async function selectPeriod(periodId) {
    completionMessage = "";
    state.periodId = periodId;
    state.selectedGroup = null;
    state.selectedMetric = null;
    if (state.scope === "formality") {
        state.demo = "ready";
        render();
        await loadCatalogPreview();
    }
    else {
        await loadSelection();
    }
    void loadProvinceBenchmarks();
}
async function loadProvinceBenchmarks() {
    const requestedPeriodId = state.periodId;
    const requestedScope = state.scope;
    const requestedFormalityId = data.formality.id;
    const periods = [period(), previousPeriodFor()].filter((item) => Boolean(item));
    let changed = false;
    await Promise.all(periods.map(async (item) => {
        const key = `${item.id}:${requestedScope}:${requestedScope === "formality" ? requestedFormalityId : "all"}`;
        if (provinceBenchmarks[key] || benchmarkLoading.has(key))
            return;
        benchmarkLoading.add(key);
        const params = new URLSearchParams({ period_type: item.type, year: String(item.year), scope: requestedScope });
        if (item.value !== null && item.value !== undefined)
            params.set("period_value", String(item.value));
        if (requestedScope === "formality" && requestedFormalityId)
            params.set("formality_id", requestedFormalityId);
        try {
            const response = await fetch(`/api/v1/dashboard/province-rankings?${params.toString()}`);
            if (response.ok) {
                provinceBenchmarks[key] = await response.json();
                changed = true;
            }
        }
        catch (error) {
            console.error(error);
        }
        finally {
            benchmarkLoading.delete(key);
        }
    }));
    if ((changed || state.modal === "brief") && state.periodId === requestedPeriodId && state.demo === "normal")
        render();
}
function announceCollectionComplete() {
    completionMessage = "Dữ liệu theo thủ tục hành chính đã được thống kê xong và sẵn sàng để xem.";
    if ("Notification" in window && Notification.permission === "granted") {
        new Notification("QD766 · Thống kê hoàn tất", { body: completionMessage });
    }
}
function pollCollectionJob(jobId, requestId, requestedKey) {
    window.setTimeout(async () => {
        try {
            const response = await fetch(`/api/v1/collection-jobs/${encodeURIComponent(jobId)}`);
            if (!response.ok)
                throw new Error(`HTTP ${response.status}`);
            const job = await response.json();
            if (job.state === "succeeded") {
                announceCollectionComplete();
                const currentKey = snapshotKey(period().id, state.scope, data.formality.id);
                if (currentKey === requestedKey)
                    await loadSelection();
                else
                    render();
                return;
            }
            if (job.state === "failed" || job.state === "halted") {
                if (requestId !== selectionRequest)
                    return;
                pendingMessage = job.error?.message ?? "Yêu cầu cập nhật dữ liệu đã dừng và cần quản trị viên kiểm tra.";
                state.demo = "error";
                render();
                return;
            }
            if (requestId === selectionRequest) {
                pendingMessage = job.state === "running" ? "Hệ thống đang thu thập tuần tự và kiểm tra dữ liệu." : "Yêu cầu đang chờ đến lượt xử lý.";
                state.demo = "queued";
                render();
            }
            pollCollectionJob(jobId, requestId, requestedKey);
        }
        catch (error) {
            if (requestId !== selectionRequest)
                return;
            console.error(error);
            pendingMessage = "Chưa đọc được trạng thái hàng đợi. Vui lòng kiểm tra lại.";
            state.demo = "error";
            render();
        }
    }, 3000);
}
async function requestCollection(requestId) {
    const selected = period();
    const requestBody = { periodType: selected.type, year: selected.year, periodValue: selected.value ?? null, scope: state.scope, provinceCode: catalogProvinceCode() };
    if (state.scope === "formality" && data.formality.id) {
        requestBody.formalityId = data.formality.id;
        requestBody.formalityCode = data.formality.code;
    }
    const response = await fetch("/api/v1/dashboard/requests", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(requestBody) });
    if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(typeof problem.detail === "string" ? problem.detail : `HTTP ${response.status}`);
    }
    const result = await response.json();
    if (requestId !== selectionRequest)
        return;
    if (result.state === "ready") {
        await loadSelection();
        return;
    }
    pendingMessage = result.message;
    state.demo = result.circuitState === "open" ? "blocked" : "queued";
    render();
    if (result.circuitState !== "open" && result.jobId) {
        pollCollectionJob(result.jobId, requestId, snapshotKey(selected.id, state.scope, data.formality.id));
    }
}
async function submitStatistics() {
    if (state.scope !== "formality")
        return;
    if (catalogPreview.mode === "filtered") {
        if (!catalogPreview.selected)
            return;
        await requestFilteredBatch();
        return;
    }
    if (!catalogPreview.selectedId)
        return;
    const requestId = ++selectionRequest;
    completionMessage = "";
    pendingMessage = "Đang gửi yêu cầu thống kê...";
    state.demo = "loading";
    render();
    try {
        await requestCollection(requestId);
    }
    catch (error) {
        if (requestId !== selectionRequest)
            return;
        console.error(error);
        pendingMessage = error instanceof Error ? error.message : String(error);
        state.demo = "error";
        render();
    }
}
function batchPeriod(batch) {
    if (batch.periodType === "month")
        return `Tháng ${batch.periodValue}/${batch.year}`;
    if (batch.periodType === "quarter")
        return `Quý ${batch.periodValue}/${batch.year}`;
    return `Năm ${batch.year}`;
}
async function requestFilteredBatch() {
    const requestId = ++selectionRequest;
    const selected = period();
    state.demo = "loading";
    render();
    const payload = { provinceCode: catalogProvinceCode(), periodType: selected.type, year: selected.year, periodValue: selected.value ?? null, includeInternal: true };
    if (catalogPreview.level)
        payload.level = catalogPreview.level;
    if (catalogPreview.field)
        payload.field = catalogPreview.field;
    if (catalogPreview.query.trim())
        payload.query = catalogPreview.query.trim();
    try {
        const response = await fetch("/api/v1/formality-batches", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        if (!response.ok) {
            const problem = await response.json().catch(() => ({}));
            throw new Error(typeof problem.detail === "string" ? problem.detail : `HTTP ${response.status}`);
        }
        const batch = await response.json();
        if (requestId !== selectionRequest)
            return;
        if (batch.state === "succeeded") {
            announceCollectionComplete();
            state.demo = "ready";
            await loadCatalogPreview();
            return;
        }
        pendingMessage = `Batch gồm ${int(batch.totalItems)} TTHC đã được lưu. ${int(batch.availableItems)} TTHC đã có dữ liệu; hệ thống đang xử lý tuần tự phần còn thiếu.`;
        state.demo = "queued";
        render();
        pollFormalityBatch(batch.id, requestId);
    }
    catch (error) {
        if (requestId !== selectionRequest)
            return;
        console.error(error);
        pendingMessage = error instanceof Error ? error.message : String(error);
        state.demo = "error";
        render();
    }
}
function pollFormalityBatch(batchId, requestId) {
    window.setTimeout(async () => {
        try {
            const response = await fetch(`/api/v1/formality-batches/${encodeURIComponent(batchId)}`);
            if (!response.ok)
                throw new Error(`HTTP ${response.status}`);
            const batch = await response.json();
            const finished = batch.availableItems + batch.completedItems;
            if (batch.state === "succeeded") {
                completionMessage = `Đã hoàn tất thống kê ${int(batch.totalItems)} TTHC; ${int(batch.availableItems)} TTHC được dùng lại từ PostgreSQL.`;
                if ("Notification" in window && Notification.permission === "granted")
                    new Notification("QD766 · Batch thống kê hoàn tất", { body: completionMessage });
                if (requestId === selectionRequest) {
                    state.demo = "ready";
                    await loadCatalogPreview();
                }
                else
                    render();
                return;
            }
            if (batch.state === "failed" || batch.state === "halted") {
                if (requestId === selectionRequest) {
                    pendingMessage = `Batch đã dừng tại ${int(finished)}/${int(batch.totalItems)} TTHC. Tiến độ đã được lưu để tiếp tục sau.`;
                    state.demo = "blocked";
                    render();
                }
                return;
            }
            if (requestId === selectionRequest) {
                pendingMessage = `Đã hoàn thành ${int(finished)}/${int(batch.totalItems)} TTHC. Hệ thống chỉ xử lý một TTHC tại một thời điểm.`;
                state.demo = "queued";
                render();
            }
            pollFormalityBatch(batchId, requestId);
        }
        catch (error) {
            if (requestId === selectionRequest) {
                console.error(error);
                pendingMessage = "Chưa đọc được tiến độ batch. Có thể kiểm tra lại trong màn hình Vận hành.";
                state.demo = "error";
                render();
            }
        }
    }, 3000);
}
async function loadCatalogPreview() {
    const requestId = ++catalogPreviewRequest;
    const selected = period();
    catalogPreview.loading = true;
    catalogPreview.error = null;
    if (state.scope === "formality") {
        state.demo = "ready";
        render();
    }
    const params = new URLSearchParams({ period_type: selected.type, year: String(selected.year), include_internal: "true", offset: String(catalogPreview.offset), limit: "100" });
    if (selected.value !== null && selected.value !== undefined)
        params.set("period_value", String(selected.value));
    if (catalogPreview.level)
        params.set("level", catalogPreview.level);
    if (catalogPreview.field)
        params.set("field", catalogPreview.field);
    if (catalogPreview.query.trim())
        params.set("q", catalogPreview.query.trim());
    try {
        const response = await fetch(`/api/v1/province-catalog/${catalogProvinceCode()}/preview?${params.toString()}`);
        if (!response.ok) {
            const problem = await response.json().catch(() => ({}));
            throw new Error(typeof problem.detail === "string" ? problem.detail : `HTTP ${response.status}`);
        }
        const body = await response.json();
        if (requestId !== catalogPreviewRequest)
            return;
        catalogPreview.loading = false;
        catalogPreview.selected = body.counts.selected;
        catalogPreview.available = body.counts.available;
        catalogPreview.missing = body.counts.missing;
        catalogPreview.fields = body.fields;
        catalogPreview.items = body.items;
    }
    catch (error) {
        if (requestId !== catalogPreviewRequest)
            return;
        catalogPreview.loading = false;
        catalogPreview.error = error instanceof Error ? error.message : String(error);
    }
    if (state.scope === "formality" && state.demo === "ready")
        render();
}
async function loadSelection() {
    const requestId = ++selectionRequest;
    const selected = period();
    const key = snapshotKey(selected.id, state.scope, data.formality.id);
    if (data.snapshots[key]) {
        state.demo = "normal";
        render();
        return;
    }
    state.demo = "loading";
    render();
    const params = new URLSearchParams({ period_type: selected.type, year: String(selected.year), scope: state.scope, root_department_id: data.province.id });
    if (selected.value !== null && selected.value !== undefined)
        params.set("period_value", String(selected.value));
    if (state.scope === "formality" && data.formality.id)
        params.set("formality_id", data.formality.id);
    try {
        const response = await fetch(`/api/v1/dashboard/selection?${params.toString()}`);
        if (response.status === 404) {
            if (requestId !== selectionRequest)
                return;
            if (state.scope === "formality") {
                pendingMessage = "";
                state.demo = "ready";
                render();
                return;
            }
            await requestCollection(requestId);
            return;
        }
        if (!response.ok) {
            const problem = await response.json().catch(() => ({}));
            throw new Error(typeof problem.detail === "string" ? problem.detail : `HTTP ${response.status}`);
        }
        const body = await response.json();
        if (requestId !== selectionRequest)
            return;
        body.snapshot.delivery = body.metadata;
        data.snapshots[key] = body.snapshot;
        mergeUnits(body.snapshot);
        state.demo = "normal";
    }
    catch (error) {
        if (requestId !== selectionRequest)
            return;
        console.error(error);
        state.demo = "error";
    }
    render();
}
async function openProvince(rootDepartmentId, requestId) {
    const response = await fetch(`/api/v1/dashboard?root_department_id=${encodeURIComponent(rootDepartmentId)}`);
    if (!response.ok)
        throw new Error(`HTTP ${response.status}`);
    const loaded = normalizeLoadedData(await response.json());
    if (requestId !== selectionRequest)
        return;
    const initialPeriod = initialPeriodFor(loaded);
    if (!initialPeriod)
        throw new Error("Tỉnh/thành phố chưa có kỳ báo cáo hoàn chỉnh");
    data = loaded;
    pendingProvinceId = "";
    document.title = `Phân tích Bộ chỉ số 766 · ${data.province.name.replace(/^UBND\s+/i, "")}`;
    catalogPreview = { loading: false, error: null, level: "", field: "", query: "", fields: [], selected: 0, available: 0, missing: 0, items: [], selectedId: null, offset: 0, mode: "single" };
    state = { ...state, periodId: initialPeriod.id, scope: "all", unitId: data.defaultUnitId, selectedGroup: null, selectedMetric: null, search: "", demo: "normal", modal: "none" };
    void loadProvinceBenchmarks();
    scrollTo(0, 0);
}
async function switchProvince(rootDepartmentId) {
    if (rootDepartmentId === data.province.id)
        return;
    const requestId = ++selectionRequest;
    pendingProvinceId = rootDepartmentId;
    ++catalogPreviewRequest;
    completionMessage = "";
    pendingMessage = "Đang chuyển dữ liệu tỉnh/thành phố...";
    state.demo = "loading";
    render();
    try {
        const option = provinceOptions.find(item => item.id === rootDepartmentId);
        if (option && !option.available) {
            pendingProvinceId = "";
            pendingMessage = `Dữ liệu chi tiết của ${option.name} chưa được lịch hệ thống cập nhật. Việc lựa chọn tỉnh không tạo yêu cầu thu thập mới.`;
            state.demo = "blocked";
        }
        else {
            await openProvince(rootDepartmentId, requestId);
        }
    }
    catch (error) {
        if (requestId !== selectionRequest)
            return;
        pendingProvinceId = "";
        console.error(error);
        pendingMessage = error instanceof Error ? error.message : String(error);
        state.demo = "error";
    }
    render();
}
async function start() {
    const productionSite = document.querySelector('meta[name="qd766-deployment"]')?.getAttribute("content") === "public";
    try {
        const policyResponse = await fetch("/api/v1/access-policy");
        if (productionSite && !policyResponse.ok)
            throw new Error("Website chưa kết nối được backend HTTPS máy cơ quan.");
        if (policyResponse.ok) {
            const policy = await policyResponse.json();
            if (productionSite && policy.publicReadOnly !== true)
                throw new Error("Backend chưa bật chế độ truy cập công khai an toàn.");
            publicReadOnly = Boolean(policy.publicReadOnly);
            loginRequired = Boolean(policy.loginRequired);
            googleLoginEnabled = Boolean(policy.googleLoginEnabled);
        }
        if (googleLoginEnabled || loginRequired) {
            const meResponse = await fetch("/api/v1/auth/me");
            if (meResponse.ok)
                signedInUser = await meResponse.json();
            else if (meResponse.status !== 401)
                throw new Error("Chưa kiểm tra được phiên đăng nhập. Vui lòng thử lại.");
            if (loginRequired && (!signedInUser || !signedInUser.provinceId)) {
                root.innerHTML = `<main class="content"><div class="empty-state"><h2>${signedInUser ? "Tài khoản đang chờ duyệt" : "Đăng nhập QĐ766"}</h2><p>${signedInUser ? "Quản trị viên cần gán tỉnh/cơ quan cho tài khoản trước khi tra cứu." : "Đăng nhập Google để xem dữ liệu của tỉnh/cơ quan được phân quyền."}</p>${!signedInUser && googleLoginEnabled ? `<a class="btn primary" href="/api/v1/auth/google/start">Đăng nhập Google</a>` : ""}${signedInUser ? `<button class="btn" data-action="logout">Đăng xuất</button>` : ""}${new URLSearchParams(location.search).get("login") === "failed" ? `<p>Đăng nhập không thành công hoặc phiên xác nhận đã hết hạn. Vui lòng thử lại.</p>` : ""}</div></main>`;
                bind();
                return;
            }
        }
        const [apiResponse, provincesResponse] = await Promise.all([fetch("/api/v1/dashboard"), fetch("/api/v1/dashboard/provinces")]);
        if (provincesResponse.ok)
            provinceOptions = await provincesResponse.json();
        if (apiResponse.ok) {
            data = normalizeLoadedData(await apiResponse.json());
        }
        else {
            if (publicReadOnly || productionSite)
                throw new Error("Chưa tải được dữ liệu thật từ máy chủ. Không dùng dữ liệu mẫu thay thế.");
            const fixtureResponse = await fetch("./data/snapshots.json");
            if (!fixtureResponse.ok)
                throw new Error(`API HTTP ${apiResponse.status}; fixture HTTP ${fixtureResponse.status}`);
            data = normalizeLoadedData(await fixtureResponse.json());
        }
        const initialPeriod = initialPeriodFor(data);
        if (!initialPeriod)
            throw new Error("Chưa có kỳ báo cáo ban đầu hoàn chỉnh");
        state = { screen: "overview", periodId: initialPeriod.id, scope: "all", unitId: data.defaultUnitId, peerDimension: "total", selectedGroup: null, selectedMetric: null, search: "", demo: "normal", modal: "none" };
        document.title = `Phân tích Bộ chỉ số 766 · ${data.province.name.replace(/^UBND\s+/i, "")}`;
        render();
        void loadProvinceBenchmarks();
    }
    catch (error) {
        root.innerHTML = `<main class="content"><div class="empty-state"><h2>Không thể tải dữ liệu</h2><p>${esc(error instanceof Error ? error.message : error)}</p><p>${productionSite ? "Vui lòng thử lại sau hoặc liên hệ quản trị viên. Website không sử dụng dữ liệu mẫu thay cho dữ liệu thật." : "Hãy kiểm tra máy chủ cục bộ và dữ liệu đầu vào."}</p></div></main>`;
    }
}
void start();
//# sourceMappingURL=app.js.map