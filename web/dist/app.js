import { allUnitTotals, buildSuggestions, buildUnitView, immediatePeers, peerStats, similarVolumePeers, snapshotFor } from "./analytics.js";
const root = document.querySelector("#app");
if (!root)
    throw new Error("Thiếu app root");
const screens = [
    { id: "overview", label: "Tổng quan", icon: "⌂" }, { id: "time", label: "Theo thời gian", icon: "↗" },
    { id: "peers", label: "Trong tỉnh", icon: "≋" }, { id: "procedure", label: "Theo TTHC", icon: "▦" },
    { id: "suggestions", label: "Gợi ý", icon: "◇" }, { id: "quality", label: "Chất lượng dữ liệu", icon: "✓" },
];
let data;
let state;
let selectionRequest = 0;
function normalizeLoadedData(loaded) {
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
const unitOptions = () => {
    const groups = [
        ["PROVINCE_TOTAL", "Kết quả chung toàn tỉnh"],
        ["PROVINCE", "Sở, ban, ngành"],
        ["COMMUNE", "Xã, phường"],
    ];
    return groups.map(([level, label]) => `<optgroup label="${label}">${data.units.filter(item => item.departmentLevel === level).map(item => `<option value="${esc(item.departmentId)}" ${item.departmentId === state.unitId ? "selected" : ""}>${esc(item.departmentName)}</option>`).join("")}</optgroup>`).join("");
};
const parameterLabels = {
    averageScore: "Điểm đánh giá trung bình", avgProcessingDays: "Số ngày xử lý trung bình",
    classifiedPetitions: "Số phản ánh, kiến nghị đã phân loại", scoreDelta: "Mức thay đổi điểm",
    totalDossierFinancialObligation: "Hồ sơ có nghĩa vụ tài chính",
    totalDossierOnlineFormalityPaymentSuccess: "Hồ sơ thanh toán trực tuyến thành công theo thủ tục",
    totalDossierOnlinePaymentSuccess: "Hồ sơ thanh toán trực tuyến thành công",
    totalDossiers: "Tổng số hồ sơ", totalFeeDossierFormality: "Hồ sơ có phát sinh phí, lệ phí",
    totalFeeDossierFormalityDistinct: "Hồ sơ có phí, lệ phí không trùng lặp",
    totalFeeFormality: "Thủ tục có phát sinh phí, lệ phí", totalOnTime: "Hồ sơ giải quyết đúng hạn",
    totalOverdue: "Hồ sơ quá hạn", totalPetitions: "Tổng số phản ánh, kiến nghị", totalReceived: "Tổng hồ sơ tiếp nhận",
};
function nav() {
    return `<aside class="sidebar"><div class="brand"><span class="brand-mark">766</span><span><strong>Phân tích QĐ766</strong><small>Phục vụ cơ quan hành chính</small></span></div><div class="nav-label">Không gian làm việc</div><nav class="nav" aria-label="Điều hướng chính">${screens.map((item) => `<button data-nav="${item.id}" class="${state.screen === item.id ? "active" : ""}" aria-current="${state.screen === item.id ? "page" : "false"}"><span class="nav-icon" aria-hidden="true">${item.icon}</span><span>${item.label}</span></button>`).join("")}</nav><div class="side-meta"><div><span class="sync-dot"></span>Dữ liệu đã cập nhật</div><div>Toàn tỉnh · Sở, ngành · Xã, phường</div><div>Kết quả từ hệ thống công bố</div></div></aside>`;
}
function context() {
    const selectedPeriod = period();
    const sameType = data.periods.filter(item => item.type === selectedPeriod.type && item.year === selectedPeriod.year);
    const years = [...new Set(data.periods.map(item => item.year))].sort((a, b) => b - a);
    return `<header class="contextbar"><div class="context-fields"><label class="field unit"><span>Cơ quan, đơn vị</span><select id="unit-select">${unitOptions()}</select></label><label class="field compact"><span>Loại kỳ</span><select id="period-type"><option value="month" ${selectedPeriod.type === "month" ? "selected" : ""}>Tháng</option><option value="quarter" ${selectedPeriod.type === "quarter" ? "selected" : ""}>Quý</option><option value="year" ${selectedPeriod.type === "year" ? "selected" : ""}>Năm</option></select></label><label class="field compact"><span>Kỳ cụ thể</span><select id="period-value">${sameType.map(item => `<option value="${item.id}" ${item.id === state.periodId ? "selected" : ""}>${item.type === "month" ? `Tháng ${item.value}` : item.type === "quarter" ? `Quý ${item.value}` : "Cả năm"}</option>`).join("")}</select></label><label class="field compact"><span>Năm</span><select id="report-year">${years.map(year => `<option value="${year}" ${year === selectedPeriod.year ? "selected" : ""}>${year}</option>`).join("")}</select></label><label class="field"><span>Phạm vi thủ tục</span><select id="scope-select"><option value="all" ${state.scope === "all" ? "selected" : ""}>Tất cả thủ tục hành chính</option><option value="formality" ${state.scope === "formality" ? "selected" : ""}>${esc(data.formality.code)} · TTHC mẫu</option></select></label></div><div class="context-actions"><button class="btn" data-action="open-quality">● Dữ liệu đầy đủ</button><button class="btn" data-action="export">Xuất</button><button class="btn primary" data-action="brief">Báo cáo lãnh đạo</button></div></header>`;
}
function shell(content) {
    const periodNotice = period().provisional ? `<div class="period-notice" role="status"><strong>Số liệu tạm thời</strong><span>Kỳ báo cáo này chưa kết thúc. Kết quả có thể thay đổi khi hệ thống nguồn cập nhật dữ liệu.</span></div>` : "";
    const loaded = data.snapshots[`${state.periodId}:${state.scope}`];
    const staleNotice = loaded?.delivery?.stale ? `<div class="period-notice stale" role="status"><strong>Chưa cập nhật được</strong><span>${esc(loaded.delivery.message ?? "Đang sử dụng bản dữ liệu hoàn chỉnh gần nhất.")}</span></div>` : "";
    root.innerHTML = `<div class="app-shell">${nav()}<div class="workspace">${context()}<main class="content">${staleNotice}${periodNotice}${content}</main></div>${state.modal === "brief" ? briefModal() : state.modal === "export" ? exportModal() : ""}</div>`;
    bind();
}
function unavailable(kind) {
    if (kind === "loading")
        return `${title("Đang tải dữ liệu", "Đang chuẩn hóa dữ liệu theo đơn vị và kỳ báo cáo.")}<div class="boot-grid"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>`;
    if (kind === "error")
        return `${title("Dữ liệu không hợp lệ", "Hệ thống chưa thể tổng hợp báo cáo ở thời điểm này.")}<div class="empty-state"><h2>Không thể hiển thị báo cáo</h2><p>Vui lòng thử lại hoặc liên hệ cán bộ quản trị dữ liệu. Các trường chưa có dữ liệu không được tính là 0.</p><button class="btn primary" data-state="normal">Thử lại</button></div>`;
    if (kind === "empty")
        return `${title("Không có dữ liệu", "Đơn vị hoặc kỳ được chọn không có bản ghi hợp lệ.")}<div class="empty-state"><h2>Không có dữ liệu cho lựa chọn hiện tại</h2><p>Hãy đổi kỳ báo cáo hoặc phạm vi TTHC. Giá trị null được giữ nguyên và không tham gia xếp hạng.</p><button class="btn" data-state="normal">Về dữ liệu thật</button></div>`;
    return `${title("Chưa đủ dữ liệu lịch sử", "Hệ thống chưa có chuỗi kỳ đồng nhất để so sánh.")}<div class="empty-state"><h2>Cần tối thiểu hai kỳ cùng loại</h2><p>Hiện có Tháng 8/2026, Quý III/2026 và Năm 2026. Ba kỳ này khác độ dài nên không được ghép thành một xu hướng.</p><button class="btn" data-state="normal">Quay lại báo cáo</button></div>`;
}
function render() {
    if (state.demo !== "normal")
        return shell(unavailable(state.demo));
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
    const suggestions = buildSuggestions(view);
    const priority = suggestions.filter((item) => item.severity === "critical" || item.severity === "warning").slice(0, 3);
    const strengths = suggestions.filter((item) => item.severity === "positive").slice(0, 3);
    const captures = snapshot().datasets.map((item) => item.capture.capturedAt).filter(Boolean).sort();
    return `${title("Tổng quan cơ quan, đơn vị", `Toàn cảnh điểm số, vị thế và việc cần ưu tiên của ${view.name}.`, "Mặc định hiển thị năm hiện tại và tất cả thủ tục hành chính.")}
  <section class="kpi-strip" aria-label="Tóm tắt điều hành"><article class="kpi"><div class="kpi-label">Tổng điểm <span class="badge ${level(view.ratio)[1]}">${level(view.ratio)[0]}</span></div><div class="kpi-value large num">${n(view.totalScore)} <small>/ ${n(view.totalMaximum)}</small></div><div class="progress"><i style="width:${Math.min(view.ratio ?? 0, 100)}%"></i></div></article><article class="kpi"><div class="kpi-label">Vị thế trong nhóm cùng cấp</div><div class="kpi-value num">${view.peer ? `${view.peer.rank}/${view.peer.total}` : "Không áp dụng"}</div><div class="kpi-sub">${view.peer ? `Phân vị P${Math.round(view.peer.percentile)}${view.peer.tiedCount > 1 ? ` · ${view.peer.tiedCount} đơn vị đồng hạng` : ""}` : "Kết quả chung toàn tỉnh không xếp hạng"}</div></article><article class="kpi"><div class="kpi-label">So với kỳ trước</div><div class="kpi-value">Chưa đủ kỳ</div><div class="kpi-sub">Cần có hai kỳ cùng loại để tính thay đổi điểm và thứ hạng</div></article><article class="kpi"><div class="kpi-label">Trạng thái dữ liệu <span class="badge good">Đầy đủ</span></div><div class="kpi-value">6/6 nhóm</div><div class="kpi-sub">Cập nhật lúc ${esc(dateTime(captures.at(-1)))}</div></article></section>
  <section class="group-grid">${view.groups.map(groupPanel).join("")}</section>
  ${overviewGroupDetail(view)}
  <section class="split"><article class="panel"><div class="panel-head"><div><h2>Vấn đề cần ưu tiên</h2><p>Dựa trên khoảng cách với trung vị và cảnh báo dữ liệu</p></div><span class="badge warn">${priority.length} phát hiện</span></div><div class="panel-body ticket-list">${priority.length ? priority.map((item) => miniTicket(item, false)).join("") : `<div class="empty-state"><h2>Chưa có cảnh báo ưu tiên</h2></div>`}</div></article><article class="panel"><div class="panel-head"><div><h2>Kết quả tốt cần duy trì</h2><p>Nhóm thuộc phân vị cao hoặc gần bão hòa điểm</p></div><span class="badge good">Điểm mạnh</span></div><div class="panel-body ticket-list">${strengths.length ? strengths.map((item) => miniTicket(item, true)).join("") : `<div class="empty-state"><h2>Chưa xác định điểm mạnh nổi bật</h2><p>Kết quả hiện tại chưa nằm trong nhóm dẫn đầu.</p></div>`}</div></article></section>`;
}
function groupPanel(group) {
    const score = scoreValue(group), maximum = group.maximum, ratio = score !== null && maximum ? score / maximum * 100 : null;
    const marker = group.peer && maximum ? Math.max(0, Math.min(100, group.peer.median / maximum * 100)) : 0;
    const stateLabel = level(ratio);
    const gap = group.peer?.gapToMedian ?? null;
    return `<button class="group-panel ${state.selectedGroup === group.id ? "selected" : ""}" data-group-detail="${group.id}" aria-pressed="${state.selectedGroup === group.id}"><div class="group-top"><h3>${esc(group.label)}</h3><span class="badge ${stateLabel[1]}">${stateLabel[0]}</span></div><div class="score-row"><div><span class="score-main num">${n(score)}</span> <span class="score-max">/ ${n(maximum)}</span></div><span class="rank">${rankText(group)}</span></div><div class="bullet" title="Thanh xanh: điểm đơn vị; vạch đen: trung vị nhóm cùng cấp"><i class="bullet-fill" style="width:${Math.min(ratio ?? 0, 100)}%"></i><b class="bullet-marker" style="left:${marker}%"></b></div><div class="bullet-labels"><span>0</span><span>Trung vị ${n(group.peer?.median)}</span><span>${n(maximum)}</span></div><div class="gap-note ${(gap ?? 0) >= 0 ? "positive" : "negative"}">${gap === null ? "Chưa có chuẩn so sánh" : `${gap >= 0 ? "+" : ""}${n(gap)}đ ${gap >= 0 ? "trên" : "dưới"} trung vị`}</div><div class="mini-meta"><span class="badge neutral">Kỳ trước: chưa đủ dữ liệu</span>${group.id === "provide-online-tree" ? `<span class="badge warn">Cách tính đang xác nhận</span>` : ""}${group.score.kind === "UNSUPPORTED_SOURCE" ? `<span class="badge info">Chưa có số liệu chi tiết</span>` : ""}</div><div class="group-link">Xem chi tiết nhóm chỉ tiêu →</div></button>`;
}
function overviewGroupDetail(view) {
    const group = view.groups.find(item => item.id === state.selectedGroup) ?? view.groups[0];
    if (!group)
        return "";
    const entity = group.entity;
    if (!entity)
        return `<section class="panel group-detail"><div class="panel-head"><div><h2>Chi tiết ${esc(group.label)}</h2><p>Chưa có số liệu chi tiết cho lựa chọn hiện tại.</p></div></div></section>`;
    const metricRows = entity.metrics.map(m => `<tr><td>${esc(m.name)}</td><td class="num">${int(m.numerator)}</td><td class="num">${int(m.denominator)}</td><td class="num">${pct(m.ratio)}</td><td class="num">${n(m.apiScore)}</td><td class="num">${n(m.apiMaxScore)}</td><td class="num lost">${m.apiScore !== null && m.apiMaxScore !== null ? n(Math.max(0, m.apiMaxScore - m.apiScore)) : "N/A"}</td></tr>`);
    const valueRows = Object.entries(entity.parameters).filter(([, value]) => value !== null).map(([key, value]) => `<tr><td>${esc(parameterLabels[key] ?? "Số liệu nghiệp vụ thành phần")}</td><td colspan="3" class="num">${esc(typeof value === "number" ? int(value) : value)}</td><td colspan="3">Được sử dụng để theo dõi và phân tích kết quả</td></tr>`);
    const rows = [...metricRows, ...valueRows];
    const selected = data.units.find(item => item.departmentId === state.unitId);
    const comparable = (group.dataset?.children ?? []).filter(item => item.departmentLevel === selected?.departmentLevel && item.apiScore !== null).sort((a, b) => (b.apiScore ?? 0) - (a.apiScore ?? 0));
    const position = comparable.findIndex(item => item.departmentId === state.unitId);
    const nearby = position < 0 ? [] : comparable.slice(Math.max(0, position - 2), Math.min(comparable.length, position + 3));
    const lost = entity.apiScore !== null && entity.apiMaxScore !== null ? Math.max(0, entity.apiMaxScore - entity.apiScore) : null;
    return `<section class="panel group-detail" id="group-detail"><div class="panel-head"><div><p class="eyebrow">Chi tiết nhóm chỉ tiêu</p><h2>${esc(group.label)}</h2><p>${esc(view.name)} · ${esc(period().label)}</p></div><div class="detail-summary"><strong class="num">${n(entity.apiScore)} / ${n(entity.apiMaxScore)}</strong><span>${rankText(group)}</span></div></div><div class="detail-columns"><div><h3>Kết quả các chỉ tiêu thành phần</h3><div class="table-wrap"><table class="metric-table"><thead><tr><th>Chỉ tiêu hoặc số liệu nghiệp vụ</th><th>Số lượng đạt</th><th>Tổng số</th><th>Tỷ lệ</th><th>Điểm ghi nhận</th><th>Điểm tối đa</th><th>Điểm chưa đạt</th></tr></thead><tbody>${rows.length ? rows.join("") : `<tr><td colspan="7">Nhóm này chưa có số liệu thành phần để hiển thị.</td></tr>`}</tbody><tfoot><tr><td colspan="4">Tổng điểm</td><td class="num">${n(entity.apiScore)}</td><td class="num">${n(entity.apiMaxScore)}</td><td class="num lost">${n(lost)}</td></tr></tfoot></table></div></div><aside class="comparison-card"><h3>So với đơn vị cùng cấp</h3>${group.peer ? `<div class="comparison-kpi"><span>Trung vị</span><strong class="num">${n(group.peer.median)}</strong></div><div class="comparison-kpi"><span>Chênh lệch</span><strong class="num ${(group.peer.gapToMedian) >= 0 ? "positive" : "negative"}">${group.peer.gapToMedian >= 0 ? "+" : ""}${n(group.peer.gapToMedian)}</strong></div><div class="nearby-list">${nearby.map((item, index) => `<div class="peer-row ${item.departmentId === state.unitId ? "mine" : ""}"><span>${esc(item.departmentName)}</span><b class="num">${n(item.apiScore)}</b><small>Hạng ${1 + comparable.filter(other => (other.apiScore ?? 0) > (item.apiScore ?? 0) + .005).length}</small></div>`).join("")}</div>` : `<div class="empty-state"><h2>Không áp dụng xếp hạng</h2><p>Kết quả chung toàn tỉnh không so hạng với cơ quan trực thuộc.</p></div>`}</aside></div></section>`;
}
function miniTicket(item, good) { return `<div class="mini-ticket"><i class="ticket-dot ${good ? "good" : ""}"></i><div><strong>${esc(item.finding)}</strong><p>${esc(item.evidence)} ${esc(item.action)}</p></div></div>`; }
function time() {
    const samples = data.periods.filter(p => Boolean(data.snapshots[`${p.id}:${state.scope}`])).map((p) => ({ p, v: buildUnitView(data, p.id, state.scope, state.unitId) }));
    return `${title("So sánh theo thời gian", "Theo dõi biến động điểm, thứ hạng và đóng góp của từng nhóm chỉ tiêu.", "Chỉ so sánh các kỳ cùng loại và đã kết thúc kỳ báo cáo.")}<div class="banner warn"><span>!</span><div><strong>Chưa đủ dữ liệu lịch sử để kết luận xu hướng</strong><p>Hiện có một kỳ tháng, một kỳ quý và một kỳ năm. Hệ thống không ghép các kỳ có độ dài khác nhau thành một chuỗi và không tạo số liệu minh họa.</p></div></div><div class="tabs"><button class="active">Tổng điểm</button><button>6 nhóm chỉ tiêu</button><button>Chỉ tiêu thành phần</button></div><section class="panel"><div class="panel-head"><div><h2>Chuỗi điểm và thứ hạng</h2><p>Chế độ: 6 kỳ · so với kỳ liền trước</p></div><div class="segmented"><button class="active">6 kỳ</button><button>12 kỳ</button><button>24 kỳ</button></div></div><div class="chart-placeholder"><div class="chart-message"><strong>Chưa có ít nhất hai kỳ cùng loại</strong><p>Biểu đồ xu hướng, phân tích nguyên nhân tăng giảm và chỉ số ổn định sẽ hiển thị khi có thêm dữ liệu lịch sử.</p></div></div></section><section class="panel" style="margin-top:12px"><div class="panel-head"><div><h2>Các kỳ hiện có</h2><p>Hiển thị độc lập để người dùng xem kết quả; không dùng làm chuỗi so sánh.</p></div><span class="badge info">Số liệu đã ghi nhận</span></div><div class="panel-body sample-grid">${samples.map(({ p, v }) => `<article class="sample-card"><span>${esc(p.label)} · ${state.scope === "all" ? "Tất cả TTHC" : data.formality.code}</span><strong class="num">${n(v.totalScore)} / ${n(v.totalMaximum)}</strong><span>${rankText(v)}</span></article>`).join("")}</div></section>`;
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
    const rows = entity.metrics.length ? entity.metrics.map(m => `<tr><td>${esc(m.name)}</td><td class="num">${int(m.numerator)}</td><td class="num">${int(m.denominator)}</td><td class="num">${pct(m.ratio)}</td><td class="num">${n(m.apiScore)}</td><td class="num">${n(m.apiMaxScore)}</td><td class="num lost">${m.apiScore !== null && m.apiMaxScore !== null ? n(Math.max(0, m.apiMaxScore - m.apiScore)) : "N/A"}</td></tr>`).join("") : Object.entries(entity.parameters).map(([key, value]) => `<tr><td>${esc(parameterLabels[key] ?? "Chỉ số nghiệp vụ")}</td><td colspan="3" class="num">${esc(typeof value === "number" ? int(value) : value)}</td><td class="num">—</td><td class="num">—</td><td class="num">—</td></tr>`).join("");
    const lost = entity.apiScore !== null && entity.apiMaxScore !== null ? Math.max(0, entity.apiMaxScore - entity.apiScore) : null;
    return `<section class="panel" style="margin-bottom:12px"><div class="panel-head"><div><h2>${esc(group.label)}</h2><p>${group.dataset?.schemaKind === "parameters" ? "Hiển thị các số liệu nghiệp vụ thành phần; chưa quy đổi lại điểm khi công thức chưa được xác nhận." : "Kết quả chi tiết theo chỉ tiêu thành phần."}</p></div><span class="badge ${group.id === "provide-online-tree" ? "warn" : "info"}">${n(entity.apiScore)} / ${n(entity.apiMaxScore)}</span></div><div class="table-wrap"><table class="metric-table"><thead><tr><th>Chỉ tiêu hoặc số liệu nghiệp vụ</th><th>Số lượng đạt</th><th>Tổng số</th><th>Tỷ lệ</th><th>Điểm ghi nhận</th><th>Điểm tối đa</th><th>Điểm chưa đạt</th></tr></thead><tbody>${rows || `<tr><td colspan="7">Chưa có số liệu chi tiết.</td></tr>`}</tbody><tfoot><tr><td colspan="4">Tổng điểm</td><td class="num">${n(entity.apiScore)}</td><td class="num">${n(entity.apiMaxScore)}</td><td class="num lost">${n(lost)}</td></tr></tfoot></table></div></section>`;
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
    return `${title("Độ tin cậy của số liệu", "Theo dõi mức độ đầy đủ và các lưu ý khi sử dụng kết quả.", "Các trường không có số liệu, bằng 0 và không áp dụng được phân biệt rõ.")}<section class="quality-grid"><article class="quality-card"><h3>Mức độ đầy đủ</h3><strong class="num">${snap.status.loadedGroups.length}/${snap.status.requiredGroups.length}</strong><p>${snap.status.state === "complete" ? "Đã có đủ sáu nhóm chỉ tiêu của kỳ đang xem." : "Một số nhóm chỉ tiêu chưa có đủ số liệu."}</p></article><article class="quality-card"><h3>Chưa có số liệu</h3><strong class="num">${missing}</strong><p>Các trường này hiển thị “Không có dữ liệu” và không được tính là 0.</p></article><article class="quality-card"><h3>Giá trị bằng 0</h3><strong class="num">${zeros}</strong><p>Đây là giá trị đã ghi nhận bằng 0, khác với trường hợp chưa có dữ liệu.</p></article><article class="quality-card"><h3>Số lượng hồ sơ quá ít</h3><strong class="num">${small}</strong><p>Một hồ sơ có thể làm tỷ lệ thay đổi mạnh; cần thận trọng khi đánh giá.</p></article><article class="quality-card"><h3>Không áp dụng ở cấp xã</h3><strong>Đang rà soát</strong><p>Tiêu chí không áp dụng được hưởng điểm tối đa theo quy định; nhãn sẽ hiển thị sau khi đối chiếu chính xác từng chỉ tiêu.</p></article><article class="quality-card"><h3>Giới hạn hiện tại</h3><strong class="num">2</strong><p>Mức độ hài lòng chưa tách theo TTHC; cách quy đổi chi tiết điểm DVC trực tuyến đang chờ xác nhận.</p></article></section><section class="panel" style="margin-top:12px"><div class="panel-head"><div><h2>Thời điểm cập nhật theo nhóm chỉ tiêu</h2><p>Giúp người dùng biết số liệu đang xem được cập nhật khi nào.</p></div><span class="badge good">Đã cập nhật</span></div><div class="table-wrap"><table><thead><tr><th>Nhóm chỉ tiêu</th><th>Thời điểm cập nhật</th><th>Trạng thái</th></tr></thead><tbody>${snap.datasets.map(d => `<tr><td>${esc(d.label)}</td><td class="num">${esc(dateTime(d.capture.capturedAt))}</td><td><span class="badge good">Đầy đủ</span></td></tr>`).join("")}</tbody></table></div></section>`;
}
function briefModal() {
    const view = unit(), list = buildSuggestions(view).filter(x => x.severity === "critical" || x.severity === "warning").slice(0, 3);
    return `<div class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Báo cáo ngắn cho lãnh đạo"><div class="modal"><div class="modal-top no-print"><strong>Báo cáo lãnh đạo · 1 trang</strong><div><button class="btn small" data-action="print">In / PDF</button> <button class="btn small" data-action="close-modal">Đóng</button></div></div><article class="brief"><p class="eyebrow">${esc(view.name)} · ${esc(period().label)}</p><h1>Báo cáo nhanh Bộ chỉ số 766</h1><p class="muted">Phạm vi ${state.scope === "all" ? "tất cả thủ tục hành chính" : data.formality.code}</p><section class="kpi-strip"><div class="kpi"><div class="kpi-label">Tổng điểm</div><div class="kpi-value large num">${n(view.totalScore)}/${n(view.totalMaximum)}</div></div><div class="kpi"><div class="kpi-label">Thứ hạng</div><div class="kpi-value num">${view.peer ? `${view.peer.rank}/${view.peer.total}` : "Không áp dụng"}</div></div><div class="kpi"><div class="kpi-label">Phân vị</div><div class="kpi-value num">${view.peer ? `P${Math.round(view.peer.percentile)}` : "—"}</div></div><div class="kpi"><div class="kpi-label">So kỳ trước</div><div class="kpi-value">Chưa đủ kỳ</div></div></section><div class="brief-groups">${view.groups.map(g => `<div class="brief-item"><span>${esc(g.label)}</span><strong class="num">${n(scoreValue(g))}/${n(g.maximum)}</strong></div>`).join("")}</div><h2>Ba việc cần chú ý</h2>${list.length ? list.map((x, i) => `<p><strong>${i + 1}. ${esc(x.finding)}</strong><br><span class="muted">${esc(x.evidence)} ${esc(x.action)}</span></p>`).join("") : `<p>Chưa phát hiện cảnh báo ưu tiên từ các thông tin hiện có.</p>`}<p class="muted">Lưu ý: chưa có hai kỳ cùng loại để xác nhận xu hướng; cách quy đổi chi tiết điểm DVC trực tuyến đang chờ xác nhận.</p></article></div></div>`;
}
function exportModal() {
    return `<div class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Trung tâm xuất báo cáo"><div class="modal"><div class="modal-top"><strong>Xuất dữ liệu và báo cáo</strong><button class="btn small" data-action="close-modal">Đóng</button></div><div class="brief"><p class="eyebrow">${esc(unit().name)} · ${esc(period().label)}</p><h1>Chọn định dạng</h1><p class="muted">Một số định dạng đang được hoàn thiện trước khi cung cấp cho người dùng.</p><div class="quality-grid" style="margin-top:18px"><article class="quality-card"><h3>Dữ liệu dạng bảng</h3><strong>CSV</strong><p>Điểm, thứ hạng, số liệu so sánh và trạng thái dữ liệu.</p><button class="btn small" disabled>Đang hoàn thiện</button></article><article class="quality-card"><h3>Bảng làm việc</h3><strong>Excel</strong><p>Gồm tổng quan, sáu nhóm chỉ tiêu và bảng so sánh.</p><button class="btn small" disabled>Đang hoàn thiện</button></article><article class="quality-card"><h3>Báo cáo lãnh đạo</h3><strong>PDF</strong><p>Mở báo cáo một trang, sau đó chọn In / PDF.</p><button class="btn small primary" data-action="brief">Mở báo cáo</button></article></div></div></div></div>`;
}
function bind() {
    document.querySelectorAll("[data-nav]").forEach(el => el.addEventListener("click", () => { state.screen = el.dataset.nav; state.demo = "normal"; render(); scrollTo(0, 0); }));
    document.querySelectorAll("[data-state]").forEach(el => el.addEventListener("click", () => { state.demo = el.dataset.state; render(); }));
    document.querySelectorAll("[data-dimension]").forEach(el => el.addEventListener("click", () => { state.peerDimension = el.dataset.dimension; render(); }));
    document.querySelectorAll("[data-group-detail]").forEach(el => el.addEventListener("click", () => { state.selectedGroup = el.dataset.groupDetail; render(); document.querySelector("#group-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }); }));
    document.querySelector("#unit-select")?.addEventListener("change", e => { state.unitId = e.target.value; render(); });
    document.querySelector("#period-type")?.addEventListener("change", e => { const type = e.target.value; const currentYear = period().year; const matches = data.periods.filter(item => item.type === type && item.year === currentYear); const fallback = data.periods.filter(item => item.type === type); const match = matches.at(-1) ?? fallback.at(-1); if (match)
        void selectPeriod(match.id); });
    document.querySelector("#period-value")?.addEventListener("change", e => { void selectPeriod(e.target.value); });
    document.querySelector("#report-year")?.addEventListener("change", e => { const year = Number(e.target.value); const matches = data.periods.filter(item => item.type === period().type && item.year === year); const match = matches.at(-1); if (match)
        void selectPeriod(match.id); });
    document.querySelector("#scope-select")?.addEventListener("change", e => { state.scope = e.target.value; void loadSelection(); });
    document.querySelector("#peer-search")?.addEventListener("input", e => { state.search = e.target.value; render(); });
    document.querySelectorAll("[data-action=brief]").forEach(el => el.addEventListener("click", () => { state.modal = "brief"; render(); }));
    document.querySelector("[data-action=export]")?.addEventListener("click", () => { state.modal = "export"; render(); });
    document.querySelector("[data-action=close-modal]")?.addEventListener("click", () => { state.modal = "none"; render(); });
    document.querySelector("[data-action=print]")?.addEventListener("click", () => window.print());
    document.querySelector("[data-action=open-quality]")?.addEventListener("click", () => { state.screen = "quality"; render(); });
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
    state.periodId = periodId;
    await loadSelection();
}
async function loadSelection() {
    const requestId = ++selectionRequest;
    const selected = period();
    const key = `${selected.id}:${state.scope}`;
    if (data.snapshots[key]) {
        state.demo = "normal";
        render();
        return;
    }
    state.demo = "loading";
    render();
    const params = new URLSearchParams({ period_type: selected.type, year: String(selected.year), scope: state.scope });
    if (selected.value !== null && selected.value !== undefined)
        params.set("period_value", String(selected.value));
    if (state.scope === "formality" && data.formality.id)
        params.set("formality_id", data.formality.id);
    try {
        const response = await fetch(`/api/v1/dashboard/selection?${params.toString()}`);
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
async function start() {
    try {
        const apiResponse = await fetch("/api/v1/dashboard");
        if (apiResponse.ok) {
            data = normalizeLoadedData(await apiResponse.json());
        }
        else {
            const fixtureResponse = await fetch("./data/snapshots.json");
            if (!fixtureResponse.ok)
                throw new Error(`API HTTP ${apiResponse.status}; fixture HTTP ${fixtureResponse.status}`);
            data = normalizeLoadedData(await fixtureResponse.json());
        }
        const initialPeriod = [...data.periods].reverse().find(item => item.type === "year" && Boolean(data.snapshots[`${item.id}:all`])) ?? [...data.periods].reverse().find(item => Boolean(data.snapshots[`${item.id}:all`]));
        if (!initialPeriod)
            throw new Error("Chưa có kỳ báo cáo ban đầu hoàn chỉnh");
        state = { screen: "overview", periodId: initialPeriod.id, scope: "all", unitId: data.defaultUnitId, peerDimension: "total", selectedGroup: "transparency", search: "", demo: "normal", modal: "none" };
        render();
    }
    catch (error) {
        root.innerHTML = `<main class="content"><div class="empty-state"><h2>Không thể tải dữ liệu</h2><p>${esc(error instanceof Error ? error.message : error)}. Hãy mở website qua máy chủ cục bộ và kiểm tra web/data/snapshots.json.</p></div></main>`;
    }
}
void start();
//# sourceMappingURL=app.js.map