import { allUnitTotals, peerStats, buildSuggestions, buildUnitView, previousAvailablePeriod, snapshotFor, snapshotForUnit, snapshotKey } from "./analytics.js";
import { analyzeOnlineScore } from "./online-scoring.js";
import { analyzeProgressScore } from "./progress-scoring.js";
import { analysisExcelFilename, buildAnalysisWorkbook } from "./excel-export.js";
import { buildLeadershipReport, buildLeadershipWorkbook, leadershipColors, leadershipUpdatedLabel } from "./leadership-report.js";
import { parameterLabels } from "./parameter-labels.js";
import { composition, gauge, gaugeLevel, groupColors, groupIcon, icon, trendChart } from "./bento.js";
import { referenceNotice, renderFormulaReference } from "./formula-reference.js";
import { renderPeerList } from './peer-list.js';
import { renderPaidAnalysis, bindPaidAnalysis, clearPaidAnalysis, stopPaidAnalysisPolling } from './paid-analysis.js';
import { latestPeriod } from './period-choice.js';
import { CollectionTracker } from "./collection-tracker.js";
import { cleanLoginSearch } from "./login-url.js";
import { loginView } from "./login-view.js";
import { openPersonalCredits, requestCreditDisplay } from "./personal-credits.js";
import { accountMenu, bindAccountMenu } from "./account-menu.js";
import { collectionCopy, insufficientCreditMessage } from "./collection-copy.js";
import { changeTone, rankImprovement } from "./change-tone.js";
import { overviewTabs, overviewTabItems, adjacentGroup } from "./overview-tabs.js";
import { bindComparisonExports } from "./comparison-export.js";
import { openGroupExport } from './group-export.js';
import { mountTrialRegistration } from './trial-registration.js';
import { pageLoader } from './page-loader.js';
import { agencyComparison, orderAgencies } from './agency-comparison.js';
import { annualDailyComparison } from './annual-daily-comparison.js';
import { onlineIndicators } from './online-indicators.js';
import { RecentDashboard } from './recent-dashboard.js';
const root = document.querySelector("#app");
const recentDashboards = new RecentDashboard();
if (!root)
    throw new Error("Thiếu app root");
const screens = [
    { id: "overview", label: "Tổng quan", icon: "⌂" }, { id: "time", label: "So sánh theo thời gian", icon: "↗" },
    { id: "peers", label: "So sánh theo cơ quan", icon: "≋" }, { id: "procedure", label: "Theo TTHC", icon: "▦" },
    { id: "suggestions", label: "Gợi ý", icon: "◇" }, { id: "quality", label: "Chất lượng dữ liệu", icon: "✓" },
    { id: "formulas", label: "Công thức tính", icon: "∑" },
    { id: "operations", label: "Vận hành", icon: "⚙" },
];
let publicReadOnly = false;
let paidRequestsEnabled = false;
let geminiAnalysisEnabled = false;
let loginRequired = false;
let googleLoginEnabled = false;
let localSimulation = false;
let localGoogleTrial = false;
let signedInUser = null;
let data;
let state;
let overviewTab = "overview";
let agencyLevel = null;
const dailyHistoryCache = new Map();
const annualObservationDates = new Map();
let selectedFormulaGroup = "transparency";
let selectionRequest = 0;
let pendingMessage = "";
let completionMessage = "";
let pendingProvinceId = "";
let searchableSelects = [];
const hiddenTrendGroups = new Set();
let operationData = { loading: false, error: null, circuitState: "unknown", circuitReason: null, snapshotCount: 0, latestSnapshotAt: null, jobs: [], batches: [], provinceBatches: [] };
let provinceOptions = [];
let provinceBenchmarks = {};
const benchmarkLoading = new Set();
let catalogPreview = { loading: false, error: null, level: "", field: "", query: "", fields: [], selected: 0, available: 0, missing: 0, items: [], selectedId: null, offset: 0, mode: "single" };
let catalogPreviewRequest = 0;
let catalogSearchTimer = 0;
let library = [];
let libraryLoading = false, libraryError = "";
let libraryRequest = 0;
let collectionTab = "new";
let myRequests = [];
let historyError = "", historyLoading = false, historyTimer = 0;
let pendingRequestCount = null;
let acquisitionMessage = "";
let creditQuote = null;
let confirmationToken = "";
let toastTimer = 0;
let submittingQuote = false;
let unreadNotifications = 0;
let submittingCollection = false;
const selectionKey = () => `${data.province.id}:${snapshotKey(state.periodId, state.scope, data.formality.id)}`;
const collectionTracker = new CollectionTracker((request, complete) => {
    if (complete) {
        announceCollectionComplete(request.label);
        void loadLibrary();
        if (request.key === selectionKey()) {
            if (request.kind === "job") {
                delete data.snapshots[snapshotKey(state.periodId, state.scope, data.formality.id)];
                void loadSelection();
                return;
            }
            state.demo = "ready";
            void loadCatalogPreview();
            return;
        }
    }
    if (request.key === selectionKey() && !["normal", "ready"].includes(state.demo)) {
        pendingMessage = request.message;
        state.demo = ["failed", "halted", "cancelled", "canceled"].includes(request.state) ? "error" : "queued";
    }
    render();
}, async (url) => {
    const response = await fetch(url, { signal: AbortSignal.timeout(15000) });
    if (!response.ok)
        throw new Error(`HTTP ${response.status}`);
    return response.json();
}, (callback, delay) => window.setTimeout(callback, delay));
function collectionNotices() {
    const labels = { queued: "Đang chờ", running: "Đang xử lý", blocked: "Chờ kết nối nguồn", succeeded: "Hoàn thành", failed: "Thất bại", halted: "Đã dừng", cancelled: "Đã hủy", canceled: "Đã hủy", unavailable: "Chưa đọc được tiến độ" };
    const pending = [...collectionTracker.requests.values()].filter(request => !["succeeded", "failed", "halted", "cancelled", "canceled"].includes(request.state));
    const count = paidRequestsEnabled ? myRequests.filter(item => ["reserved", "waiting", "running"].includes(item.state)).length : pending.length;
    return count || unreadNotifications ? `<button class="collection-status-pill" data-action="request-history">${count ? `${count} yêu cầu đang xử lý` : ""}${count && unreadNotifications ? " · " : ""}${unreadNotifications ? `${unreadNotifications} thông báo mới` : ""} · Xem yêu cầu</button>` : "";
}
const canAcquire = () => paidRequestsEnabled ? Boolean(signedInUser?.canCollect) : !publicReadOnly;
const libraryParams = () => {
    const selected = period();
    const params = new URLSearchParams({ period_type: selected.type, year: String(selected.year) });
    if (selected.value != null)
        params.set("period_value", String(selected.value));
    return params;
};
async function loadLibrary() {
    if (!paidRequestsEnabled && !canAcquire())
        return;
    const revision = ++libraryRequest, rootId = data.province.id, periodId = state.periodId;
    library = [];
    libraryError = "";
    libraryLoading = true;
    try {
        const params = libraryParams();
        if (!paidRequestsEnabled)
            params.set("root_department_id", rootId);
        const response = await fetch(`/api/v1/${paidRequestsEnabled ? "me/formalities" : "dashboard/formalities"}?${params}`);
        if (!response.ok)
            throw new Error("Chưa đọc được danh sách thủ tục đã khai thác.");
        const body = await response.json();
        if (revision !== libraryRequest || state.periodId !== periodId || data.province.id !== rootId)
            return;
        library = body.items;
    }
    catch (error) {
        if (revision === libraryRequest)
            libraryError = error instanceof Error ? error.message : String(error);
    }
    finally {
        if (revision === libraryRequest) {
            libraryLoading = false;
            render();
        }
    }
}
async function openAcquisition(tab = "new") {
    state.screen = "procedure";
    state.modal = "none";
    collectionTab = tab;
    acquisitionMessage = "";
    render();
    if (tab === "new")
        await loadCatalogPreview();
    else
        await loadMyRequests(true);
}
async function loadMyRequests(markRead = false) {
    if (historyLoading)
        return;
    window.clearTimeout(historyTimer);
    historyLoading = true;
    historyError = "";
    try {
        const response = await fetch(paidRequestsEnabled ? "/api/v1/me/formality-requests" : "/api/v1/collection-jobs?limit=100");
        if (!response.ok)
            throw new Error("Chưa đọc được lịch sử yêu cầu.");
        if (paidRequestsEnabled) {
            const body = await response.json();
            pendingRequestCount = body.pendingRequests ?? null;
            unreadNotifications = body.unreadNotifications ?? 0;
            const previous = new Map(myRequests.map(item => [item.id, item.state]));
            myRequests = body.items;
            const completed = myRequests.find(item => item.state === "ready" && ["waiting", "reserved", "running"].includes(previous.get(item.id) ?? ""));
            if (completed) {
                announceCollectionComplete(`${data.province.name} · ${requestPeriod(completed)} · ${completed.code}`);
                void loadLibrary();
            }
            if (signedInUser) {
                signedInUser.credits = body.availableCredits;
                signedInUser.reservedCredits = body.reservedCredits;
            }
            if (markRead && unreadNotifications) {
                const acknowledged = await fetch("/api/v1/me/notifications/read", { method: "POST", headers: { "Content-Type": "application/json", "X-QD766-CSRF": signedInUser?.csrfToken ?? "" }, body: JSON.stringify({ requestIds: myRequests.map(item => item.id) }) });
                if (acknowledged.ok)
                    unreadNotifications = 0;
            }
        }
        else {
            const rows = await response.json();
            myRequests = rows.filter(job => job.request.scope === "formality" && job.request.rootDepartmentId === data.province.id).map(job => ({ id: job.id, state: job.state, formalityId: job.request.formalityId ?? "", code: job.formalityCode ?? "", name: job.formalityName ?? "", periodType: job.request.period?.type ?? "year", year: job.request.period?.year ?? 0, periodValue: job.request.period?.month ?? job.request.period?.quarter ?? null, creditCost: null, createdAt: job.createdAt, error: null }));
        }
    }
    catch (error) {
        historyError = error instanceof Error ? error.message : String(error);
    }
    finally {
        historyLoading = false;
        render();
        if ((paidRequestsEnabled || (state.screen === "procedure" && collectionTab === "history")) && myRequests.some(r => ["waiting", "reserved", "queued", "running"].includes(r.state)))
            historyTimer = window.setTimeout(() => { void loadMyRequests(); }, 10000);
    }
}
async function openSavedFormality(item, periodId = state.periodId) {
    state.periodId = periodId;
    state.scope = "formality";
    state.screen = "overview";
    state.selectedGroup = null;
    state.selectedMetric = null;
    data.formality = { ...item };
    catalogPreview.selectedId = item.id;
    catalogPreview.mode = "single";
    saveSelectionUrl();
    await loadSelection();
    void loadLibrary();
    void loadProvinceBenchmarks();
}
function saveSelectionUrl() {
    if (typeof history === "undefined" || typeof location === "undefined")
        return;
    const params = new URLSearchParams({ province: data.province.id, period: state.periodId, scope: state.scope, unit: state.unitId });
    if (state.scope === "formality")
        params.set("formality", data.formality.id);
    history.replaceState(null, "", `${location.pathname}?${params}`);
}
function requestPeriod(item) { return item.periodType === "month" ? `Tháng ${item.periodValue}/${item.year}` : item.periodType === "quarter" ? `Quý ${item.periodValue}/${item.year}` : `Năm ${item.year}`; }
function acquisitionPage() {
    if (!canAcquire())
        return `<section class="panel"><div class="empty-state"><h2>Khai thác dữ liệu theo TTHC</h2><p>Đăng nhập tài khoản được cấp quyền để tạo yêu cầu khai thác.</p></div></section>`;
    const labels = { ready: "Hoàn thành", succeeded: "Hoàn thành", waiting: "Đang chờ", reserved: "Đang chờ", queued: "Đang chờ", running: "Đang xử lý", refunded: "Thất bại", failed: "Thất bại", halted: "Đã dừng" };
    const historyView = `<section class="panel"><div class="panel-head"><h2>${paidRequestsEnabled ? "Yêu cầu của tôi" : "Yêu cầu trên máy cơ quan"}</h2><button class="btn small" data-action="refresh-history">Làm mới</button></div>${historyError ? `<p class="collection-error">${esc(historyError)}</p>` : ""}<div class="table-wrap"><table><thead><tr><th>Thủ tục hành chính</th><th>Kỳ</th><th>Trạng thái</th><th>Credit</th><th></th></tr></thead><tbody>${myRequests.map(item => `<tr><td><b>${esc(item.code)}</b><span class="request-name" title="${esc(item.name)}">${esc(item.name)}</span></td><td>${esc(requestPeriod(item))}</td><td><span class="badge ${["ready", "succeeded"].includes(item.state) ? "good" : "neutral"}">${esc(labels[item.state] ?? item.state)}</span></td><td>${requestCreditDisplay(item.state, item.creditCost)}</td><td>${["ready", "succeeded"].includes(item.state) ? `<button class="btn small" data-view-request="${esc(item.id)}">Xem dữ liệu</button>` : ""}</td></tr>`).join("") || `<tr><td colspan="5">${historyLoading ? "Đang đọc lịch sử…" : "Chưa có yêu cầu nào."}</td></tr>`}</tbody></table></div></section>`;
    return `<header class="bento-heading"><h1>Khai thác dữ liệu TTHC</h1>${paidRequestsEnabled ? `<span class="badge ${pendingRequestCount !== null && pendingRequestCount >= 2 ? "warn" : "neutral"}">${pendingRequestCount === null ? "Tối đa 2 yêu cầu đang chờ / xử lý" : `${int(pendingRequestCount)}/2 yêu cầu đang chờ / xử lý`}</span>` : ""}<p>${esc(data.province.name)} · ${esc(period().label)}</p></header><div class="collection-tabs"><button class="btn ${collectionTab === "new" ? "primary" : ""}" data-collection-tab="new">Tạo yêu cầu</button><button class="btn ${collectionTab === "history" ? "primary" : ""}" data-collection-tab="history">${paidRequestsEnabled ? "Yêu cầu của tôi" : "Lịch sử quản trị"}</button></div>${acquisitionMessage ? `<p class="collection-feedback" role="status">${esc(acquisitionMessage)}</p>` : ""}${collectionTab === "new" ? catalogReady() : historyView}`;
}
function collectionConfirmation() {
    const selected = catalogPreview.items.find(item => item.id === catalogPreview.selectedId);
    const rows = creditQuote?.items ?? (selected ? [selected] : []);
    const copy = creditQuote ? collectionCopy(creditQuote.items) : { title: "Tra cứu dữ liệu", notice: "", button: "Tra cứu dữ liệu", mode: "new" };
    const expired = creditQuote?.blockedReason === "subscription_expired";
    return `<div class="modal-backdrop" role="dialog" aria-modal="true" aria-label="${esc(copy.title)}"><div class="modal collection-confirm">
    <div class="modal-top"><strong>${esc(copy.title)}</strong><button class="btn small" data-action="close-modal">Đóng</button></div>
    <div class="brief"><h2>${esc(period().label)} · ${esc(data.province.name)}</h2><ul>${rows.map(item => `<li><b>${esc(item.code)}</b> ${esc(item.name)}</li>`).join("")}</ul>
    ${creditQuote ? `<div class="credit-summary"><span>Credit sử dụng</span><strong>${int(creditQuote.totalCredits)} Credit</strong><span>Số dư: ${int(creditQuote.availableCredits)} Credit</span></div>
      ${expired ? '<div role="alert" style="background:#fff7ed;border:1px solid #fed7aa;border-radius:16px;padding:16px;margin:16px 0"><strong>Subscription đã hết hạn</strong><p>Gia hạn để tiếp tục khai thác. Yêu cầu chưa được gửi và không giữ Credit.</p></div>' : `<p role="status">${esc(copy.notice)}</p>`}` :
        `<p>Môi trường quản trị máy cơ quan: không thu credit. Phân quyền theo tài khoản chỉ được kiểm chứng khi bật đăng nhập.</p>`}
    <p class="collection-error" ${acquisitionMessage ? 'role="alert"' : ""}>${esc(acquisitionMessage)}</p>
    <button class="btn primary" data-action="${copy.mode === "new" ? "confirm-collection" : "open-owned-quote"}" ${expired || submittingCollection ? "disabled" : ""}>${submittingCollection ? "Đang gửi…" : esc(copy.button)}</button>
    ${expired ? '<button class="btn" data-action="renew-from-collection">Gia hạn trong Usage</button>' : ""}
    </div></div></div>`;
}
async function prepareCollection() {
    if (submittingCollection || submittingQuote || catalogPreview.loading || catalogPreview.error || !canAcquire())
        return;
    creditQuote = null;
    acquisitionMessage = "";
    const quotedContext = data.province.id + ":" + state.periodId;
    const ids = catalogPreview.mode === "single" ? [catalogPreview.selectedId].filter(Boolean) : catalogPreview.items.map(item => item.id);
    if (!ids.length)
        return;
    if (paidRequestsEnabled) {
        if (catalogPreview.mode === "filtered" && (catalogPreview.selected > 50 || catalogPreview.selected !== ids.length)) {
            acquisitionMessage = "Hãy thu hẹp bộ lọc: tối đa 50 TTHC mỗi yêu cầu.";
            render();
            return;
        }
        submittingQuote = true;
        render();
        try {
            const selected = period();
            const response = await fetch("/api/v1/me/collection-quote", { method: "POST", headers: { "Content-Type": "application/json", "X-QD766-CSRF": signedInUser?.csrfToken ?? "" }, body: JSON.stringify({ periodType: selected.type, year: selected.year, periodValue: selected.value ?? null, formalityIds: ids }) });
            const body = await response.json();
            if (!response.ok && !(response.status === 403 && body.blockedReason === "subscription_expired")) {
                throw new Error(body.detail ?? "Chưa xác định được Credit sử dụng.");
            }
            const result = body;
            if (quotedContext !== data.province.id + ":" + state.periodId) {
                acquisitionMessage = "Kỳ hoặc tỉnh đã thay đổi; vui lòng xác nhận lại yêu cầu tra cứu.";
                return;
            }
            creditQuote = result;
            confirmationToken = crypto.randomUUID();
        }
        catch (error) {
            acquisitionMessage = error instanceof Error ? error.message : String(error);
            return;
        }
        finally {
            submittingQuote = false;
            render();
        }
    }
    state.modal = "collection";
    render();
}
async function confirmCollection() {
    if (submittingCollection)
        return;
    if (!paidRequestsEnabled) {
        const selected = catalogPreview.items.find(item => item.id === catalogPreview.selectedId);
        if (selected)
            data.formality = { id: selected.id, code: selected.code, name: selected.name };
        state.scope = "formality";
        state.modal = "none";
        await submitStatistics();
        acquisitionMessage = state.demo === "error" ? pendingMessage : "Yêu cầu đã được tiếp nhận. Bạn có thể lấy thủ tục khác hoặc xem lịch sử.";
        render();
        return;
    }
    if (!creditQuote || creditQuote.blockedReason)
        return;
    const insufficient = insufficientCreditMessage(creditQuote.totalCredits, creditQuote.availableCredits);
    if (insufficient) {
        acquisitionMessage = insufficient;
        render();
        return;
    }
    submittingCollection = true;
    render();
    try {
        const response = await fetch("/api/v1/me/formality-requests", { method: "POST", headers: { "Content-Type": "application/json", "X-QD766-CSRF": signedInUser?.csrfToken ?? "" }, body: JSON.stringify({ quote: creditQuote.quote, token: confirmationToken }) });
        const body = await response.json();
        if (!response.ok)
            throw new Error(body.detail ?? "Chưa gửi được yêu cầu.");
        if (signedInUser) {
            signedInUser.credits = body.availableCredits;
            signedInUser.reservedCredits = body.reservedCredits;
        }
        state.modal = "none";
        collectionTab = "history";
        catalogPreview.selectedId = null;
        acquisitionMessage = "Yêu cầu đã được lưu. Dữ liệu hoàn tất sẽ xuất hiện trong Thủ tục đã khai thác.";
        void loadLibrary();
        await loadMyRequests();
    }
    catch (error) {
        acquisitionMessage = error instanceof Error ? error.message : String(error);
    }
    finally {
        submittingCollection = false;
        render();
    }
}
function collectionLabel() {
    return `${data.province.name} · ${period().label} · ${catalogPreview.mode === "filtered" ? `${int(catalogPreview.selected)} TTHC sau lọc` : `${data.formality.code} · ${data.formality.name}`}`;
}
const catalogProvinceCode = () => data.province.code ?? provinceOptions.find(item => item.id === data.province.id)?.provinceCode ?? "";
const initialPeriodFor = (loaded) => latestPeriod(loaded.periods.filter(item => item.type === "year" && Boolean(loaded.snapshots[`${item.id}:all`]))) ?? latestPeriod(loaded.periods.filter(item => Boolean(loaded.snapshots[`${item.id}:all`])));
function normalizeLoadedData(loaded) {
    if (loaded.formality.id) {
        for (const item of loaded.periods) {
            const legacyKey = `${item.id}:formality`;
            if (loaded.snapshots[legacyKey]) {
                const legacy = loaded.snapshots[legacyKey];
                // Legacy dashboard keys may refer to a different TTHC than the default selector.
                if (legacy.formalityId)
                    loaded.snapshots[snapshotKey(item.id, "formality", legacy.formalityId)] = legacy;
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
    const html = baseNav();
    const collection = publicReadOnly && paidRequestsEnabled && canAcquire() ? `<button type="button" data-nav="procedure" class="${state.screen === "procedure" ? "active" : ""}"><span class="nav-icon" aria-hidden="true">${icon("document")}</span><span>Theo TTHC</span></button>` : "";
    const admin = signedInUser?.role === "admin" ? `<button type="button" data-action="open-admin" title="Quản trị dùng thử"><span class="nav-icon" aria-hidden="true">${icon("shield")}</span><span>Quản trị dùng thử</span></button>` : "";
    return html.replace("</nav>", collection + admin + "</nav>").replace(/<div class="side-meta">[\s\S]*?<\/div><\/div><\/aside>$/, signedInUser ? accountMenu(signedInUser) + "</aside>" : '$&');
}
function baseNav() {
    return `<aside class="sidebar"><div class="brand"><span class="brand-mark"><img class="cchc-logo" src="/assets/logo-cchc.png" alt="Cải cách hành chính" width="40" height="40"></span><span><strong>Phân tích QĐ766</strong><small>Phục vụ cơ quan hành chính</small></span></div><div class="nav-label">Không gian làm việc</div><nav class="nav" aria-label="Điều hướng chính">${screens.filter(item => !publicReadOnly || !["procedure", "operations", "suggestions"].includes(item.id)).map((item) => `<button data-nav="${item.id}" class="${state.screen === item.id ? "active" : ""}" aria-current="${state.screen === item.id ? "page" : "false"}"><span class="nav-icon" aria-hidden="true">${icon(({ overview: "shield", time: "chart", peers: "monitor", procedure: "document", suggestions: "star", quality: "shield", operations: "clock", formulas: "document" })[item.id])}</span><span>${item.label}</span></button>`).join("")}</nav><div class="side-meta"><div><span class="sync-dot"></span>Dữ liệu đã cập nhật</div><div>Toàn tỉnh · Sở, ngành · Xã, phường</div><div>Kết quả từ hệ thống công bố</div></div></aside>`;
}
function context() {
    if (state.screen === "formulas")
        return `<header class="contextbar formula-context"><strong>Sổ tay Bộ chỉ số 766</strong><span>Tra cứu công thức · Không phụ thuộc tỉnh hoặc kỳ đang chọn</span></header>`;
    const selectedPeriod = period();
    const sameType = data.periods.filter(item => item.type === selectedPeriod.type && item.year === selectedPeriod.year)
        .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
    const years = [...new Set(data.periods.map(item => item.year))].sort((a, b) => b - a);
    const formalityScopeLabel = catalogPreview.mode === "single" && catalogPreview.selectedId ? `${data.formality.code} · ${data.formality.name}` : catalogPreview.mode === "filtered" && catalogPreview.selected ? `${int(catalogPreview.selected)} TTHC sau lọc` : "Theo thủ tục hành chính";
    const canSubmit = !publicReadOnly && !submittingCollection && !collectionTracker.hasActive(selectionKey()) && state.scope === "formality" && ["ready", "normal"].includes(state.demo) && (catalogPreview.mode === "filtered" ? catalogPreview.selected > 0 : Boolean(catalogPreview.selectedId));
    const selectedProvinceId = pendingProvinceId || data.province.id;
    const provinceItems = (provinceOptions.length ? provinceOptions : [{ id: data.province.id, name: data.province.name, departmentCode: null, provinceCode: data.province.code ?? null, snapshotCount: 0, latestSnapshotAt: null, available: true }]).slice().sort((left, right) => alphabet.compare(displayProvinceName(left.name), displayProvinceName(right.name))).map(item => `<option value="${esc(item.id)}" ${item.id === selectedProvinceId ? "selected" : ""}>${esc(displayProvinceName(item.name))}${item.available ? "" : " · chưa có dữ liệu"}</option>`).join("");
    return `<header class="contextbar"><div class="context-fields"><label class="field province"><span>Tỉnh/Thành phố</span><select id="province-select">${provinceItems}</select></label><label class="field unit"><span>Cơ quan, đơn vị</span><select id="unit-select">${unitOptions()}</select></label><label class="field compact"><span>Loại kỳ</span><select id="period-type"><option value="month" ${selectedPeriod.type === "month" ? "selected" : ""}>Tháng</option><option value="quarter" ${selectedPeriod.type === "quarter" ? "selected" : ""}>Quý</option><option value="year" ${selectedPeriod.type === "year" ? "selected" : ""}>Năm</option></select></label><label class="field compact"><span>Kỳ cụ thể</span><select id="period-value">${sameType.map(item => `<option value="${item.id}" ${item.id === state.periodId ? "selected" : ""}>${item.type === "month" ? `Tháng ${item.value}` : item.type === "quarter" ? `Quý ${item.value}` : "Cả năm"}</option>`).join("")}</select></label><label class="field compact"><span>Năm</span><select id="report-year">${years.map(year => `<option value="${year}" ${year === selectedPeriod.year ? "selected" : ""}>${year}</option>`).join("")}</select></label><label class="field"><span>Phạm vi thủ tục</span><select id="scope-select"><option value="all" ${state.scope === "all" ? "selected" : ""}>Tất cả thủ tục hành chính</option>${!canAcquire() ? "" : `<option value="formality" ${state.scope === "formality" ? "selected" : ""}>Theo thủ tục hành chính</option>`}</select></label></div><div class="context-bottom">${state.scope === "formality" && state.screen !== "procedure" ? `<label class="field saved-formality"><span>Thủ tục đã khai thác</span><select id="saved-formality"><option value="">${libraryLoading ? "Đang đọc danh sách…" : "Chọn thủ tục đã khai thác"}</option>${library.map(item => `<option value="${esc(item.id)}" ${item.id === data.formality.id ? "selected" : ""}>${esc(item.code + " · " + item.name)}</option>`).join("")}</select></label>` : ""}<div class="context-actions">${!signedInUser && googleLoginEnabled ? `<a class="btn" href="/api/v1/auth/google/start">Đăng nhập Google</a>` : ""}${canAcquire() ? `<button class="btn" data-action="new-collection">+ Tra cứu TTHC khác</button>` : ""}${collectionNotices()}<button class="btn" data-action="open-quality">${data.snapshots[snapshotKey(state.periodId, state.scope, data.formality.id)]?.delivery?.detailsAvailable === false ? "● Chỉ có điểm tổng hợp" : "● Chất lượng dữ liệu"}</button><button class="btn" data-action="export">Xuất dữ liệu</button><button class="btn primary" data-action="brief">Báo cáo lãnh đạo</button></div></div></header>`;
}
function shell(content) {
    root.setAttribute("aria-busy", "false");
    // Async search refreshes replace the shell; preserve only the active search input.
    // Never reclaim focus if the user has moved to another control in the meantime.
    const activeQuery = ["catalog-query", "peer-search"].includes(document.activeElement?.id ?? "") ? document.activeElement : null;
    const queryCaret = activeQuery ? { start: activeQuery.selectionStart, end: activeQuery.selectionEnd, direction: activeQuery.selectionDirection } : null;
    const loaded = data.snapshots[snapshotKey(state.periodId, state.scope, data.formality.id)];
    const formalityNotice = state.scope === "formality" && catalogPreview.mode === "single" && catalogPreview.selectedId ? `<div class="formality-notice" role="status"><strong>Thủ tục đang chọn</strong><span><b>${esc(data.formality.code)}</b>${esc(data.formality.name)}</span></div>` : state.scope === "formality" && catalogPreview.mode === "filtered" && catalogPreview.selected > 0 ? `<div class="formality-notice batch" role="status"><strong>Phạm vi đang chọn</strong><span><b>${int(catalogPreview.selected)} TTHC</b>${catalogPreview.level === "ward" ? "Cấp xã" : catalogPreview.level === "province" ? "Cấp tỉnh" : "Cấp tỉnh và cấp xã"}${catalogPreview.field ? ` · ${esc(catalogPreview.field)}` : ""}${catalogPreview.query ? ` · Từ khóa “${esc(catalogPreview.query)}”` : ""}</span></div>` : "";
    const periodNotice = state.demo === "normal" && state.screen !== "operations" && loaded && period().provisional ? `<div class="period-notice" role="status"><strong>Số liệu tạm thời</strong><span>Kỳ báo cáo này chưa kết thúc. Kết quả có thể thay đổi khi hệ thống nguồn cập nhật dữ liệu.</span></div>` : "";
    const staleNotice = loaded?.delivery?.stale ? `<div class="period-notice stale" role="status"><strong>Chưa cập nhật được</strong><span>${esc(loaded.delivery.message ?? "Đang sử dụng bản dữ liệu hoàn chỉnh gần nhất.")}</span></div>` : "";
    const completedNotice = completionMessage ? `<div class="period-notice success" role="status"><strong>Thống kê hoàn tất</strong><span>${esc(completionMessage)}</span><button class="btn small" data-action="dismiss-completion">Đóng</button></div>` : "";
    searchableSelects.forEach(control => control.destroy());
    searchableSelects = [];
    const timingNotice = loaded?.delivery?.detailsAvailable === false ? `<div class="period-notice" role="status"><strong>Chỉ có điểm tổng hợp tỉnh</strong><span>Kỳ này có đủ điểm 6 nhóm để so sánh tỉnh; chưa có chỉ tiêu thành phần hoặc điểm sở/ngành, xã/phường. Chọn kỳ không tạo yêu cầu thu thập.</span></div>` : state.demo === "normal" && loaded?.delivery?.result === "national-summary" && loaded.delivery.capturedAt !== loaded.delivery.detailsCapturedAt ? `<div class="period-notice" role="status"><strong>Hai thời điểm cập nhật</strong><span>Điểm tỉnh: ${esc(dateTime(loaded.delivery.capturedAt))}. Chi tiết chỉ tiêu và điểm cơ quan trực thuộc: ${esc(dateTime(loaded.delivery.detailsCapturedAt))}. Số liệu thành phần có thể chưa khớp điểm tỉnh mới nhất.</span></div>` : "";
    const notices = staleNotice + periodNotice + timingNotice;
    const comparisonHint = ["time", "peers"].includes(state.screen) ? '<p>Chỉ so sánh cùng loại kỳ, cùng phạm vi. Ô trống không được tính là 0; thứ hạng chỉ tính trên các đơn vị có đủ điểm. Biến động hạng cần cùng tập đơn vị giữa hai kỳ.</p>' : "";
    const qualityHint = state.screen === "quality" ? '<p>Thiếu dữ liệu không được tính là 0. Với số lượng hồ sơ nhỏ, tỷ lệ có thể biến động mạnh. Mức chi tiết phụ thuộc dữ liệu nguồn.</p>' : "";
    const pageNotes = state.screen === "formulas" || (state.screen === "overview" && state.demo === "normal") ? "" :
        ["time", "peers", "procedure", "quality"].includes(state.screen) ?
            (notices || comparisonHint || qualityHint ? `<details class="comparison-notes"><summary>Lưu ý</summary>${notices + comparisonHint + qualityHint}</details>` : "") : notices;
    root.innerHTML = `<div class="app-shell enterprise-mode ${["overview", "formulas"].includes(state.screen) ? "bento-mode" : ""}">${nav()}<div class="workspace">${context()}<main class="content">${pageNotes}${content}</main></div>${state.modal === "brief" ? briefModal() : state.modal === "export" ? exportModal() : state.modal === "collection" ? collectionConfirmation() : ""}${completionMessage ? `<div class="collection-toast" role="status"><strong>Hoàn tất</strong><span>${esc(completionMessage)}</span><button class="btn small" data-action="dismiss-completion">Đóng</button></div>` : ""}</div>`;
    if (localSimulation)
        root.querySelector(".content")?.insertAdjacentHTML("afterbegin", '<div class="period-notice"><strong>THỬ NGHIỆM LOCAL · DỮ LIỆU MÔ PHỎNG</strong><span>Không gọi Cổng DVCQG, không trừ credit thật.</span><a class="btn small" href="/local-trial.html">Đổi tài khoản / thử kết quả job</a></div>');
    if (localGoogleTrial)
        root.querySelector(".content")?.insertAdjacentHTML("afterbegin", '<div class="period-notice"><strong>BẢN THỬ GOOGLE LOCAL</strong><span>Google thật · Dữ liệu và credit mô phỏng · Không chạy worker lấy dữ liệu thật.</span></div>');
    if (paidRequestsEnabled && signedInUser) {
        const scopeSelect = root.querySelector("#scope-select");
        if (scopeSelect && !scopeSelect.querySelector('option[value="formality"]')) {
            scopeSelect.insertAdjacentHTML("beforeend", '<option value="formality">Theo TTHC · đã khai thác</option>');
            scopeSelect.value = state.scope;
        }
    }
    bind();
    if (signedInUser)
        bindAccountMenu(signedInUser);
    if (queryCaret) {
        const query = document.getElementById(activeQuery.id);
        query?.focus({ preventScroll: true });
        if (query && queryCaret.start !== null && queryCaret.end !== null)
            query.setSelectionRange(queryCaret.start, queryCaret.end, queryCaret.direction ?? "none");
    }
}
function initSearchableSelects() {
    const settings = [
        { selector: "#province-select", placeholder: "Nhập tên tỉnh/thành phố…" },
        { selector: "#unit-select", placeholder: "Nhập tên cơ quan, đơn vị…" },
        { selector: "#catalog-field", placeholder: "Nhập tên lĩnh vực…" },
        { selector: "#saved-formality", placeholder: "Nhập mã hoặc tên thủ tục…" },
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
        return `<section class="panel"><div class="empty-state"><h2>${libraryLoading ? "Đang đọc danh sách thủ tục…" : "Chọn thủ tục đã khai thác"}</h2><p>${esc(libraryError || "Chọn thủ tục trong ô phía trên để xem lại. Chưa có thủ tục phù hợp? Hãy tạo yêu cầu lấy dữ liệu.")}</p><button class="btn primary" data-action="new-collection">Lấy dữ liệu TTHC</button></div></section>`;
    if (kind === "loading")
        return pageLoader();
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
    stopPaidAnalysisPolling();
    if (state.screen === "procedure")
        return shell(acquisitionPage());
    if (state.screen === "formulas")
        return shell(renderFormulaReference(selectedFormulaGroup));
    if (state.screen === "operations")
        return shell(operations());
    if (state.demo !== "normal")
        return shell(unavailable(state.demo));
    if (snapshot().delivery?.detailsAvailable === false && state.unitId !== data.province.id)
        return shell(`<section class="panel"><div class="empty-state"><h2>Chưa có điểm cơ quan trong kỳ này</h2><p>Hiện chỉ có điểm tổng hợp tỉnh. Chọn UBND tỉnh để xem và so sánh 6 nhóm, hoặc chọn kỳ khác có dữ liệu cơ quan.</p></div></section>`);
    const content = state.screen === "overview" ? overview()
        : state.screen === "time" ? time()
            : state.screen === "peers" ? peers()
                : state.screen === "suggestions" ? suggestions()
                    : quality();
    shell(content);
}
function analysisSelection() {
    const selected = period();
    const snap = snapshot();
    const view = unit();
    return { rootDepartmentId: data.province.id, unitId: state.unitId, periodType: selected.type, year: selected.year,
        periodValue: selected.value ?? null, scope: state.scope, capturedAt: snap.delivery?.detailsCapturedAt ?? snap.delivery?.capturedAt ?? '',
        organization: view.name, periodLabel: selected.label, availableGroups: view.groups.filter(group => group.entity?.apiScore !== null && group.entity?.apiScore !== undefined && group.entity?.apiMaxScore !== null && group.entity?.apiMaxScore !== undefined && group.entity.apiMaxScore > 0).map(group => group.id) };
}
function overview() {
    const view = unit();
    const previousPeriod = previousPeriodFor();
    const previousView = previousPeriod ? buildUnitView(data, previousPeriod.id, state.scope, state.unitId) : null;
    const currentRank = rankFor(view, state.periodId, null);
    const previousRank = previousView && previousPeriod ? rankFor(previousView, previousPeriod.id, null) : null;
    const scoreChange = previousView?.totalScore !== null && previousView?.totalScore !== undefined && view.totalScore !== null ? view.totalScore - previousView.totalScore : null;
    const rankChange = rankImprovement(previousRank?.rank, currentRank?.rank);
    const points = data.periods.filter(p => p.type === period().type && periodOrder(p) <= periodOrder(period()) && Boolean(data.snapshots[snapshotKey(p.id, state.scope, data.formality.id)]))
        .sort((a, b) => periodOrder(a) - periodOrder(b)).slice(-12).map(p => ({ label: p.label, order: periodOrder(p), view: buildUnitView(data, p.id, state.scope, state.unitId) }));
    return `<header class="bento-heading"><h1>${esc(view.name)}</h1><p>${esc(period().label)} <span>·</span> ${state.scope === "all" ? "Tất cả thủ tục hành chính" : esc(data.formality.code + " · " + data.formality.name)}</p></header>
  ${overviewStatus()}
  ${overviewTabs(overviewTab)}
  <div id="overview-tab-panel" role="tabpanel" aria-labelledby="overview-tab-${overviewTab}">
  ${overviewTab === "overview" ? `
  <section class="bento-top" aria-label="Tổng điểm và sáu nhóm chỉ tiêu"><article class="bento-card hero-card"><div class="bento-card-head"><div><h2>Điểm tổng hợp 766</h2><p>Bộ chỉ số phục vụ người dân, doanh nghiệp</p></div><span class="badge ${gaugeLevel(view.totalMaximum === 100 ? view.totalScore : view.ratio).tone}">${gaugeLevel(view.totalMaximum === 100 ? view.totalScore : view.ratio).label}</span></div>${gauge(view.totalScore, view.totalMaximum)}
  <div class="hero-comparison"><div><span>Thứ hạng cùng cấp</span><strong>${currentRank ? `${currentRank.rank}/${currentRank.total}` : "Chưa xếp hạng"}</strong><small>${currentRank ? `Phân vị P${Math.round(currentRank.percentile)}${currentRank.tiedCount > 1 ? " · đồng hạng" : ""}` : "Cùng kỳ, cùng phạm vi"}</small></div>${period().type === 'year' && state.scope === 'all' ? annualDailyComparison(dailyHistoryCache.get(dailyContext().key)?.history ?? null, annualObservationDates.get(dailyContext().key), dailyHistoryCache.get(dailyContext().key)?.loading ?? true, dailyHistoryCache.get(dailyContext().key)?.error ?? '') : `<div><span>So với kỳ trước</span><strong class="${changeTone(scoreChange)}">${scoreChange === null ? "Chưa đủ kỳ" : `${scoreChange >= 0 ? "+" : ""}${n(scoreChange)} điểm`}</strong><small>${previousPeriod ? esc(previousPeriod.label) : "Cần kỳ liền trước cùng loại"}</small></div>`}</div>
  <div class="hero-footer"><span class="${changeTone(rankChange)}">${rankChange === null ? "Chưa đủ dữ liệu biến động thứ hạng" : rankChange === 0 ? "Thứ hạng không đổi" : `Thứ hạng ${rankChange > 0 ? "tăng" : "giảm"} ${Math.abs(rankChange)} bậc`}</span><span>${view.groups.filter(g => g.score.value !== null).length}/6 nhóm có điểm</span></div></article>
  <div class="bento-pillars">${view.groups.map(groupPanel).join("")}</div></section>
  <section class="bento-charts"><article class="bento-card trend-card"><div class="bento-card-head"><div><h2>Xu hướng điểm</h2><p>Lịch sử của cơ quan đang chọn · ${period().type === "month" ? "Theo tháng" : period().type === "quarter" ? "Theo quý" : "Theo năm"}</p></div><span class="bento-icon">${icon("chart")}</span></div>${trendChart(points, data.groupOrder, hiddenTrendGroups)}</article><article class="bento-card composition-card"><div class="bento-card-head"><div><h2>Cơ cấu điểm 766</h2><p>Đóng góp của sáu nhóm chỉ tiêu</p></div></div>${composition(view)}</article></section>
  ` : overviewTab === "details" ? overviewGroupNavigator(view) + overviewGroupDetail(view) : `
  ${renderPaidAnalysis(analysisSelection(), Boolean(signedInUser), geminiAnalysisEnabled)}`}</div>`;
}
function groupTableHeading(label) {
    return `<div class="group-table-heading"><h3>${esc(label)}</h3><button type="button" class="btn group-export-button" data-group-export>Tải biểu Excel</button></div>`;
}
function overviewGroupNavigator(view) {
    const group = view.groups.find(item => item.id === state.selectedGroup);
    return `<div class="overview-group-nav" style="--group-accent:${group ? groupColors[group.id] : '#4f46e5'}" aria-label="Chuyển nhóm chỉ tiêu"><button class="btn" data-group-step="-1" aria-label="Nhóm chỉ tiêu trước"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5l-7 7 7 7M7 12h13"/></svg></button><div aria-live="polite"><strong>${esc(group?.label ?? "Tổng hợp 6 nhóm chỉ tiêu")}</strong></div><button class="btn" data-group-step="1" aria-label="Nhóm chỉ tiêu tiếp theo"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 5l7 7-7 7M4 12h13"/></svg></button></div>`;
}
function overviewStatus() {
    const delivery = snapshot().delivery;
    const captures = snapshot().datasets.map(d => d.capture.capturedAt).filter(Boolean).sort();
    const scoreAt = state.unitId === data.province.id ? delivery?.capturedAt ?? captures.at(-1) : delivery?.detailsCapturedAt ?? captures.at(-1);
    const detailsAt = delivery?.detailsAvailable === false ? null : delivery?.detailsCapturedAt ?? captures.at(-1);
    return `<details class="bento-status"><summary><span class="status-toggle">ⓘ Thông tin dữ liệu</span></summary><div class="status-explanation"><p>Điểm: ${esc(dateTime(scoreAt))} · Chi tiết: ${esc(dateTime(detailsAt))}</p>${delivery?.detailsAvailable === false ? '<p>Chỉ có điểm tổng hợp tỉnh; chưa có dữ liệu chi tiết trong kỳ này.</p>' : ''}${delivery?.stale ? '<p>Đang sử dụng bản dữ liệu hoàn chỉnh gần nhất; chưa có bản cập nhật theo lịch 04:00.</p>' : ''}${period().provisional ? '<p>Kỳ báo cáo chưa kết thúc; kết quả có thể thay đổi khi nguồn cập nhật.</p>' : ''}</div></details>`;
}
function groupPanel(group) {
    const score = scoreValue(group), maximum = group.maximum, ratio = score !== null && maximum ? score / maximum * 100 : null;
    const peer = rankFor(group, state.periodId, group.id);
    const previous = previousPeriodFor();
    const prior = previous ? buildUnitView(data, previous.id, state.scope, state.unitId).groups.find(g => g.id === group.id) : null;
    const priorScore = prior ? scoreValue(prior) : null;
    const delta = score !== null && priorScore !== null ? score - priorScore : null;
    const level = gaugeLevel(ratio);
    return `<button class="bento-card pillar-card ${state.selectedGroup === group.id ? "selected" : ""}" style="--pillar-color:${groupColors[group.id]}" data-group-detail="${group.id}" aria-pressed="${state.selectedGroup === group.id}"><div class="pillar-heading"><h3>${esc(group.label)}</h3><span class="bento-icon">${groupIcon(group.id)}</span></div><div class="pillar-score" data-score-tone="${level.tone}"><strong>${n(score)}</strong><span>/ ${n(maximum)}</span></div><div class="pillar-meta"><span class="${changeTone(delta)}">${delta === null ? "Chưa đủ kỳ trước" : `${delta >= 0 ? "+" : ""}${n(delta)} đ`}</span><span>${peer ? `Hạng ${peer.rank}/${peer.total}` : "Chưa xếp hạng"}</span></div><div class="pillar-progress" role="img" aria-label="${ratio === null ? "Chưa có tỷ lệ điểm" : `Đạt ${pct(ratio)} điểm tối đa`}"><i style="width:${Math.max(0, Math.min(ratio ?? 0, 100))}%"></i></div><div class="pillar-bottom"><span>${ratio === null ? "Chưa có điểm" : pct(ratio) + " điểm tối đa"}</span><span>${peer ? `Trung vị ${n(peer.median)} đ` : "Xem chi tiết →"}</span></div></button>`;
}
function totalPeerComparison(view) {
    const selected = data.units.find(item => item.departmentId === state.unitId);
    const isProvince = selected?.departmentLevel === "PROVINCE_TOTAL";
    const rows = isProvince
        ? (provinceBenchmarks[benchmarkCacheKey(state.periodId)] ?? []).flatMap(item => item.totalScore === null ? [] : [{ id: item.rootDepartmentId, name: item.provinceName, score: item.totalScore }])
        : allUnitTotals(snapshot(), selected?.departmentLevel ?? "COMMUNE").map(item => ({ id: item.id, name: item.name, score: item.score }));
    rows.sort((left, right) => right.score - left.score || alphabet.compare(left.name, right.name));
    const currentIndex = rows.findIndex(item => item.id === state.unitId);
    const current = rows[currentIndex];
    const stats = current && rows.length > 1 ? peerStats(rows.map(item => item.score), current.score) : null;
    const heading = isProvince ? "So sánh tổng điểm với tỉnh/thành phố khác" : "So sánh tổng điểm với đơn vị cùng cấp";
    if (!stats)
        return `<aside class="comparison-card"><h3>${heading}</h3><div class="empty-state"><h2>Chưa đủ dữ liệu so sánh</h2><p>Cần tối thiểu hai đơn vị cùng cấp, cùng kỳ và cùng phạm vi.</p></div></aside>`;
    return `<aside class="comparison-card"><h3>${heading}</h3><div class="comparison-kpi"><span>Thứ hạng tổng 6 nhóm</span><strong class="num">${stats.rank}/${stats.total}</strong></div><div class="comparison-kpi"><span>Trung vị tổng điểm</span><strong class="num">${n(stats.median)}</strong></div>${renderPeerList(rows, state.unitId)}</aside>`;
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
        const rankChange = rankImprovement(previousRank?.rank, currentRank?.rank);
        const rankChangeText = rankChange === null ? "—" : rankChange > 0 ? `↑ ${rankChange} bậc` : rankChange < 0 ? `↓ ${Math.abs(rankChange)} bậc` : "Không đổi";
        return `<tr class="selectable-row" data-group-detail="${group.id}"><td><button class="row-link">${esc(group.label)}</button></td><td class="num"><strong>${n(currentScore)}</strong> / ${n(group.maximum)}</td><td class="num">${previousPeriod ? n(previousScore) : "—"}</td><td class="num ${changeTone(scoreChange)}">${scoreChange === null ? "—" : `${scoreChange >= 0 ? "+" : ""}${n(scoreChange)}`}</td><td class="num ${changeTone(rankChange)}">${rankChangeText}</td></tr>`;
    }).join("");
    return `<section class="panel group-comparison" id="group-detail"><div class="panel-head"><div><p class="eyebrow">Tổng hợp 6 nhóm chỉ tiêu</p><h2>Điểm số và biến động theo kỳ</h2><p>${esc(view.name)} · ${esc(period().label)}${previousPeriod ? ` so với ${esc(previousPeriod.label)}` : " · chưa có kỳ trước cùng loại"}</p></div></div><div class="detail-columns"><div class="detail-metrics-card">${groupTableHeading("Điểm 6 nhóm chỉ tiêu")}<div class="table-wrap"><table class="summary-table"><thead><tr><th>Tên nhóm chỉ tiêu</th><th>Điểm số</th><th>Điểm kỳ trước</th><th>Tăng/giảm so với kỳ trước</th><th>Tăng/giảm thứ hạng</th></tr></thead><tbody>${rows}</tbody></table></div></div>${totalPeerComparison(view)}</div></section>`;
}
function onlineAnalysis(entity) {
    // Do not substitute provincial parameters for the selected child agency.
    if (entity.departmentId !== data.province.id)
        return null;
    const indicators = onlineIndicators(entity.parameters);
    if (!indicators.length)
        return null;
    const derived = indicators.map(r => `<tr><td>${esc(r.name)}<small class="online-indicator-formula">${esc(r.formula)}</small></td><td class="num">${int(r.numerator)}</td><td class="num">${int(r.denominator)}</td><td class="num">${pct(r.ratio)}</td><td colspan="3">Chưa có điểm thành phần từ nguồn</td></tr>`);
    const raw = Object.entries(entity.parameters).filter(([, value]) => value !== null).map(([key, value]) => `<tr><td>${esc(parameterLabels[key] ?? "Số liệu nghiệp vụ thành phần")}</td><td colspan="3" class="num">${esc(typeof value === "number" ? int(value) : value)}</td><td colspan="3">Tham số nguồn</td></tr>`);
    return { rows: [...derived, ...raw], catalog: "", notice: '<p class="online-indicator-note">Các tỷ lệ dưới đây tính từ tham số nguồn để đối chiếu dashboard Cổng DVCQG, không phải công thức quy đổi điểm. Điểm nhóm giữ nguyên theo Cổng công bố. Tỷ lệ DVCTT phát sinh hồ sơ là của kỳ đang chọn; biểu đồ tháng cần số liệu riêng từng tháng.</p>' };
}
function progressDetail(entity) {
    const analysis = analyzeProgressScore(entity);
    if (!analysis)
        return null;
    const progressPercent = (value) => value === null ? "—" : `${n(value)}%`;
    const formula = analysis.onTimeRatio === null || analysis.calculatedScore === null
        ? "Không tính tỷ lệ khi tổng hồ sơ tiếp nhận bằng 0."
        : `${int(analysis.totalOnTime)} / ${int(analysis.totalReceived)} × ${n(analysis.maxScore)} = ${n(analysis.calculatedScore)} điểm`;
    const averageDays = analysis.averageProcessingDays === null ? "N/A" : `${n(analysis.averageProcessingDays)} ngày`;
    const difference = analysis.matchesApi === false ? `<small class="progress-discrepancy">Chênh ${n(Math.abs(analysis.difference ?? 0), 3)} điểm so với điểm nguồn</small>` : "";
    return `<div class="progress-kpis"><article><span>Tổng hồ sơ tiếp nhận</span><strong class="num">${int(analysis.totalReceived)}</strong></article><article><span>Giải quyết đúng hạn</span><strong class="num positive">${int(analysis.totalOnTime)}</strong></article><article><span>Hồ sơ quá hạn giải quyết</span><strong class="num negative">${int(analysis.totalOverdue)}</strong></article><article><span>Giải quyết trung bình</span><strong class="num">${averageDays}</strong></article></div><div class="table-wrap"><table class="metric-table progress-table"><thead><tr><th>Nội dung</th><th>Số lượng</th><th>Tỷ lệ</th><th>Công thức</th></tr></thead><tbody><tr><td>Tổng hồ sơ tiếp nhận</td><td class="num">${int(analysis.totalReceived)} hồ sơ</td><td class="num">—</td><td>—</td></tr><tr class="selectable-row ${state.selectedMetric === "progress:on-time" ? "selected" : ""}" data-metric-detail="progress:on-time"><td><button class="row-link">Hồ sơ giải quyết đúng hạn</button></td><td class="num">${int(analysis.totalOnTime)} hồ sơ</td><td class="num positive">${progressPercent(analysis.onTimeRatio)}</td><td>Hồ sơ đúng hạn / Tổng hồ sơ tiếp nhận × 100%</td></tr><tr><td>Hồ sơ quá hạn giải quyết</td><td class="num">${int(analysis.totalOverdue)} hồ sơ</td><td class="num negative">${progressPercent(analysis.overdueRatio)}</td><td>${analysis.overdueDerived ? "Tổng hồ sơ tiếp nhận − Hồ sơ đúng hạn; " : ""}Hồ sơ quá hạn / Tổng hồ sơ tiếp nhận × 100%</td></tr><tr><td>Thời gian giải quyết trung bình</td><td class="num">${averageDays}</td><td class="num">—</td><td>Theo số liệu Cổng DVCQG</td></tr></tbody><tfoot><tr><td>Điểm tính đối chiếu</td><td colspan="2" class="num">${n(analysis.calculatedScore)} / ${n(analysis.maxScore)} điểm</td><td>${esc(formula)}${difference}</td></tr></tfoot></table></div>`;
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
    const stats = currentPoint && rows.length > 1 ? peerStats(rows.map(item => item.score), currentPoint.score) : null;
    const heading = isProvince ? "So sánh chỉ tiêu với tỉnh/thành phố khác" : "So sánh chỉ tiêu với đơn vị cùng cấp";
    if (!stats)
        return `<aside class="comparison-card"><h3>${heading}</h3><strong>${esc(currentPoint?.label ?? "Chỉ tiêu được chọn")}</strong><div class="empty-state"><h2>Chưa đủ dữ liệu so sánh</h2></div></aside>`;
    return `<aside class="comparison-card metric-comparison"><h3>${heading}</h3><strong>${esc(currentPoint?.label)}</strong><div class="comparison-kpi"><span>Điểm chỉ tiêu</span><strong class="num">${n(currentPoint?.score)}${currentPoint?.maximum === null ? "" : ` / ${n(currentPoint?.maximum)}`}</strong></div><div class="comparison-kpi"><span>Thứ hạng</span><strong class="num">${stats.rank}/${stats.total}</strong></div>${renderPeerList(rows, state.unitId)}</aside>`;
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
        const stats = benchmarkRank(state.periodId, group.id);
        if (!stats)
            return `<aside class="comparison-card"><h3>So với tỉnh/thành phố khác</h3><div class="empty-state"><h2>Chưa đủ dữ liệu liên tỉnh</h2><p>Cần có ít nhất hai tỉnh/thành phố cùng kỳ và cùng phạm vi để so sánh.</p></div></aside>`;
        return `<aside class="comparison-card"><h3>So với tỉnh/thành phố khác</h3><div class="comparison-kpi"><span>Thứ hạng</span><strong class="num">${stats.rank}/${stats.total}</strong></div><div class="comparison-kpi"><span>Trung vị các tỉnh</span><strong class="num">${n(stats.median)}</strong></div>${renderPeerList(rows, state.unitId)}</aside>`;
    }
    const comparable = (group.dataset?.children ?? []).filter(item => item.departmentLevel === selected?.departmentLevel && item.apiScore !== null).sort((a, b) => (b.apiScore ?? 0) - (a.apiScore ?? 0));
    return `<aside class="comparison-card"><h3>So với đơn vị cùng cấp</h3>${group.peer ? `<div class="comparison-kpi"><span>Trung vị</span><strong class="num">${n(group.peer.median)}</strong></div><div class="comparison-kpi"><span>Chênh lệch</span><strong class="num ${(group.peer.gapToMedian) >= 0 ? "positive" : "negative"}">${group.peer.gapToMedian >= 0 ? "+" : ""}${n(group.peer.gapToMedian)}</strong></div>${renderPeerList(comparable.map(item => ({ id: item.departmentId, name: item.departmentName, score: item.apiScore })), state.unitId)}` : `<div class="empty-state"><h2>Chưa đủ đơn vị cùng cấp</h2></div>`}</aside>`;
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
        return `<section class="panel group-detail" id="group-detail">${heading}<div class="detail-columns"><div class="detail-metrics-card progress-detail">${groupTableHeading("Kết quả các chỉ tiêu thành phần")}${referenceNotice(group.id)}${progress}</div>${comparison}</div></section>`;
    return `<section class="panel group-detail" id="group-detail">${heading}<div class="detail-columns"><div class="detail-metrics-card">${groupTableHeading("Kết quả các chỉ tiêu thành phần")}${referenceNotice(group.id)}${calculated?.notice ?? ""}<div class="table-wrap"><table class="metric-table"><thead><tr><th>Chỉ tiêu hoặc số liệu nghiệp vụ</th><th>Số lượng đạt</th><th>Tổng số</th><th>Tỷ lệ</th><th>Điểm ghi nhận</th><th>Điểm tối đa</th><th>Điểm chưa đạt</th></tr></thead><tbody>${rows.length ? rows.join("") : `<tr><td colspan="7">${esc(emptyDetailMessage)}</td></tr>`}</tbody><tfoot><tr><td colspan="4">Tổng điểm</td><td class="num">${n(entity.apiScore)}</td><td class="num">${n(entity.apiMaxScore)}</td><td class="num lost">${n(lost)}</td></tr></tfoot></table></div></div>${comparison}</div></section>`;
}
function miniTicket(item, good) { return `<div class="mini-ticket"><i class="ticket-dot ${good ? "good" : ""}"></i><div><strong>${esc(item.finding)}</strong><p>${esc(item.evidence)} ${esc(item.action)}</p></div></div>`; }
function dailyContext() {
    const unitId = state.unitId;
    return { unitId, key: [data.province.id, state.periodId, unitId].join(":") };
}
function loadDailyHistory() {
    if (!state || !data || state.scope !== "all" || state.screen !== "overview" || overviewTab !== "overview" || period().type !== "year")
        return;
    const { unitId, key } = dailyContext();
    if (!unitId || dailyHistoryCache.has(key))
        return;
    const selected = period(), entry = { loading: true, history: null, error: "" };
    dailyHistoryCache.set(key, entry);
    const query = new URLSearchParams({ root_department_id: data.province.id, unit_id: unitId, period_type: selected.type, year: String(selected.year), limit: "366", include_peers: "false" });
    if (selected.value != null)
        query.set("period_value", String(selected.value));
    void fetch("/api/v1/dashboard/daily-history?" + query).then(async (response) => {
        if (!response.ok)
            throw new Error("Chưa đọc được lịch sử theo ngày. Vui lòng thử lại.");
        const body = await response.json();
        entry.history = { days: Array.isArray(body.days) ? body.days : [], scope: "all" };
    }).catch(error => { entry.error = error instanceof Error ? error.message : "Không đọc được lịch sử ngày."; }).finally(() => {
        entry.loading = false;
        if (state?.screen === 'overview' && dailyContext().key === key)
            render();
    });
}
function time() {
    const samples = data.periods.filter(p => p.type === period().type && Boolean(data.snapshots[snapshotKey(p.id, state.scope, data.formality.id)]))
        .sort((a, b) => periodOrder(a) - periodOrder(b)).map(p => ({ p, v: buildUnitView(data, p.id, state.scope, state.unitId) }));
    const rows = samples.map(({ p, v }) => {
        const previous = previousAvailablePeriod(data, p.id, state.scope);
        const prior = previous ? buildUnitView(data, previous.id, state.scope, state.unitId) : null;
        const delta = v.totalScore !== null && prior?.totalScore !== null && prior?.totalScore !== undefined ? v.totalScore - prior.totalScore : null;
        const rank = rankFor(v, p.id, null);
        return `<tr><td>${esc(p.label)}${p.provisional ? ' <span class="badge warn">Tạm thời</span>' : ""}</td><td class="num">${n(v.totalScore)}</td><td class="num">${n(prior?.totalScore)}</td><td class="num ${changeTone(delta)}">${delta === null ? "—" : (delta >= 0 ? "+" : "") + n(delta)}</td><td class="num ${changeTone(rankImprovement(previous ? rankFor(prior, previous.id, null)?.rank : null, rank?.rank))}">${rank ? rank.rank + "/" + rank.total : "—"}</td>${v.groups.map(group => `<td class="num">${n(group.score.value)}</td>`).join("")}</tr>`;
    }).join("");
    return `${title("So sánh theo thời gian", "Điểm các kỳ cùng loại và biến động so với kỳ liền trước.", "Kỳ đang diễn ra được đánh dấu tạm thời; không ghép tháng, quý và năm.")}<section class="panel"><div class="panel-head"><div><h2>Chuỗi điểm cùng loại kỳ</h2><p>Thiếu kỳ liền trước thì không tính biến động. Thứ hạng chỉ hiển thị khi đã đọc dữ liệu so sánh của kỳ đó.</p></div></div><div class="table-wrap"><table><thead><tr><th>Kỳ</th><th>Tổng điểm</th><th>Điểm kỳ trước</th><th>Tăng/giảm điểm</th><th>Thứ hạng</th>${data.groupOrder.map(group => `<th>${esc(data.groupLabels[group])}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div></section>`;
}
function peers() {
    const selected = data.units.find(item => item.departmentId === state.unitId);
    const restricted = signedInUser?.accessTier === "agency";
    const allowed = restricted ? data.units.filter(item => item.departmentId === signedInUser?.unitId) : data.units;
    const previous = previousAvailablePeriod(data, state.periodId, state.scope);
    const prior = previous ? data.snapshots[snapshotKey(previous.id, state.scope, data.formality.id)] ?? null : null;
    const rows = agencyComparison(snapshot(), prior, data.groupOrder, allowed);
    // A one-unit access scope is not a province-wide ranking cohort.
    if (restricted)
        for (const row of rows) {
            row.rank = null;
            row.rankChange = null;
        }
    const ownLevel = selected?.departmentLevel === "COMMUNE" ? "COMMUNE" : "PROVINCE";
    const level = restricted ? ownLevel : agencyLevel ?? ownLevel;
    const visible = orderAgencies(rows.filter(row => row.level === level), state.peerDimension, state.search);
    const delta = (value) => value === null ? "—" : (value > 0 ? "+" : "") + n(Math.abs(value) < .005 ? 0 : value);
    const heading = (key, label) => `<th><button class="agency-sort ${state.peerDimension === key ? "active" : ""}" data-dimension="${key}" aria-label="Sắp xếp giảm dần theo ${esc(label)}">${esc(label)}</button></th>`;
    const tabs = ["PROVINCE", "COMMUNE"].filter(item => !restricted || item === ownLevel).map(item => `<button type="button" data-agency-level="${item}" class="${item === level ? "active" : ""}" aria-pressed="${item === level}"><i aria-hidden="true">${icon(item === 'PROVINCE' ? 'chart' : 'shield')}</i>${item === "PROVINCE" ? "Sở, ngành" : "Xã, phường"}</button>`).join("");
    return `${title("So sánh theo cơ quan", data.province.name + " · " + period().label, "")}
  <section class="panel agency-ranking"><div class="panel-head"><div><h2>Bảng xếp hạng</h2><p>${visible.length} cơ quan, đơn vị · ${previous ? "So với " + esc(previous.label) : "Chưa có kỳ liền trước"}</p></div>
  <input id="peer-search" type="search" aria-label="Tìm cơ quan, đơn vị" value="${esc(state.search)}" placeholder="Tìm cơ quan, đơn vị…"></div>
  <div class="table-toolbar"><div class="agency-levels" role="group" aria-label="Cấp cơ quan">${tabs}</div></div>
  <div class="table-wrap agency-ranking-scroll"><table><thead><tr><th>Hạng</th><th>Cơ quan, đơn vị</th>${heading("total", "Tổng điểm")}<th>Tăng/giảm điểm</th><th>Tăng/giảm hạng</th>${data.groupOrder.map(group => heading(group, data.groupLabels[group])).join("")}</tr></thead><tbody>
  ${visible.map(row => `<tr class="${row.id === state.unitId ? "mine" : ""}"><td class="num">${row.rank ?? "—"}</td><td><button class="agency-link" data-peer-unit="${esc(row.id)}">${esc(row.name)}</button></td><td class="num"><strong>${n(row.total)}</strong></td><td class="num ${changeTone(row.scoreChange)}">${delta(row.scoreChange)}</td><td class="num ${changeTone(row.rankChange)}">${row.rankChange === null ? "—" : (row.rankChange > 0 ? "+" : "") + row.rankChange}</td>${data.groupOrder.map(group => `<td class="num"><button class="agency-link" data-peer-unit="${esc(row.id)}" data-peer-group="${group}" aria-label="${esc(data.groupLabels[group])} · ${esc(row.name)}">${n(row.scores[group] ?? null)}</button></td>`).join("")}</tr>`).join("") || `<tr><td colspan="${5 + data.groupOrder.length}">Không có cơ quan, đơn vị phù hợp trong phạm vi được phép xem.</td></tr>`}
  </tbody></table></div></section>`;
}
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
        return `<section class="panel" style="margin-bottom:12px"><div class="panel-head"><div><h2>${esc(group.label)}</h2><p>Tính điểm từ tỷ lệ hồ sơ giải quyết đúng hạn; tỷ lệ quá hạn và thời gian xử lý được hiển thị để phân tích.</p></div><span class="badge good">${n(entity.apiScore)} / ${n(entity.apiMaxScore)}</span></div><div class="panel-body progress-detail"><h3>Kết quả và công thức tính điểm</h3>${referenceNotice(group.id)}${progress}</div></section>`;
    const calculated = group.id === "provide-online-tree" ? onlineAnalysis(entity) : null;
    const rows = calculated ? calculated.rows.join("") : entity.metrics.length ? entity.metrics.map(m => `<tr><td>${esc(m.name)}</td><td class="num">${int(m.numerator)}</td><td class="num">${int(m.denominator)}</td><td class="num">${pct(m.ratio)}</td><td class="num">${n(m.apiScore)}</td><td class="num">${n(m.apiMaxScore)}</td><td class="num lost">${m.apiScore !== null && m.apiMaxScore !== null ? n(Math.max(0, m.apiMaxScore - m.apiScore)) : "N/A"}</td></tr>`).join("") : Object.entries(entity.parameters).map(([key, value]) => `<tr><td>${esc(parameterLabels[key] ?? "Chỉ số nghiệp vụ")}</td><td colspan="3" class="num">${esc(typeof value === "number" ? int(value) : value)}</td><td class="num">—</td><td class="num">—</td><td class="num">—</td></tr>`).join("");
    const lost = entity.apiScore !== null && entity.apiMaxScore !== null ? Math.max(0, entity.apiMaxScore - entity.apiScore) : null;
    const description = calculated ? "Ba chỉ tiêu thành phần được tính lại để giải thích điểm; điểm Cổng công bố vẫn là giá trị chính thức." : group.dataset?.schemaKind === "parameters" ? "Hiển thị các số liệu nghiệp vụ thành phần; chưa có đủ dữ liệu để phân rã điểm." : "Kết quả chi tiết theo chỉ tiêu thành phần.";
    return `<section class="panel" style="margin-bottom:12px"><div class="panel-head"><div><h2>${esc(group.label)}</h2><p>${description}</p></div><span class="badge ${calculated ? "good" : "info"}">${n(entity.apiScore)} / ${n(entity.apiMaxScore)}</span></div>${referenceNotice(group.id)}${calculated?.notice ?? ""}<div class="table-wrap"><table class="metric-table"><thead><tr><th>Chỉ tiêu hoặc số liệu nghiệp vụ</th><th>Số lượng đạt</th><th>Tổng số</th><th>Tỷ lệ</th><th>Điểm ghi nhận</th><th>Điểm tối đa</th><th>Điểm chưa đạt</th></tr></thead><tbody>${rows || `<tr><td colspan="7">Chưa có số liệu chi tiết.</td></tr>`}</tbody><tfoot><tr><td colspan="4">Tổng điểm</td><td class="num">${n(entity.apiScore)}</td><td class="num">${n(entity.apiMaxScore)}</td><td class="num lost">${n(lost)}</td></tr></tfoot></table></div></section>`;
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
    return `${title("Độ tin cậy của số liệu", "", "")}<section class="quality-grid"><article class="quality-card"><h3>Mức độ đầy đủ điểm số</h3><strong class="num">${snap.status.loadedGroups.length}/${snap.status.requiredGroups.length}</strong></article><article class="quality-card"><h3>Chưa có số liệu</h3><strong class="num">${missing}</strong></article><article class="quality-card"><h3>Giá trị bằng 0</h3><strong class="num">${zeros}</strong></article><article class="quality-card"><h3>Số lượng hồ sơ quá ít</h3><strong class="num">${small}</strong></article></section><section class="panel" style="margin-top:12px"><div class="panel-head"><h2>Thời điểm cập nhật theo nhóm chỉ tiêu</h2></div><div class="table-wrap"><table><thead><tr><th>Nhóm chỉ tiêu</th><th>Thời điểm cập nhật</th><th>Mức dữ liệu</th></tr></thead><tbody>${coverageRows}</tbody></table></div></section>`;
}
function catalogReady() {
    const selected = catalogPreview.items.find(item => item.id === catalogPreview.selectedId) ?? null;
    const rows = catalogPreview.items.map(item => `<label class="catalog-row ${item.id === catalogPreview.selectedId && catalogPreview.mode === "single" ? "selected" : ""}">${catalogPreview.mode === "single" ? `<input type="radio" name="catalog-formality" value="${esc(item.id)}" ${item.id === catalogPreview.selectedId ? "checked" : ""}>` : `<span class="catalog-batch-mark">✓</span>`}<span><strong>${esc(item.code)}</strong><small title="${esc(item.name)}">${esc(item.name)}</small><em>${esc(item.field || "Chưa phân loại")}</em></span></label>`).join("");
    const first = catalogPreview.selected ? catalogPreview.offset + 1 : 0;
    const last = Math.min(catalogPreview.offset + catalogPreview.items.length, catalogPreview.selected);
    const canSubmit = canAcquire() && !submittingCollection && !submittingQuote && !catalogPreview.loading && !catalogPreview.error && (catalogPreview.mode === "filtered" ? catalogPreview.selected > 0 : Boolean(selected));
    return `<section class="panel catalog-panel"><div class="catalog-mode"><button class="${catalogPreview.mode === "single" ? "active" : ""}" data-catalog-mode="single">Một TTHC</button><button class="${catalogPreview.mode === "filtered" ? "active" : ""}" data-catalog-mode="filtered">Kết quả sau lọc</button></div><div class="catalog-filters"><label class="field"><span>Cấp thực hiện</span><select id="catalog-level"><option value="">Cấp tỉnh và cấp xã</option><option value="province" ${catalogPreview.level === "province" ? "selected" : ""}>Cấp tỉnh</option><option value="ward" ${catalogPreview.level === "ward" ? "selected" : ""}>Cấp xã</option></select></label><label class="field"><span>Lĩnh vực</span><select id="catalog-field"><option value="">Tất cả lĩnh vực</option>${catalogPreview.fields.map(field => `<option value="${esc(field)}" ${field === catalogPreview.field ? "selected" : ""}>${esc(field)}</option>`).join("")}</select></label><label class="field catalog-search"><span>Tìm mã hoặc tên TTHC</span><input id="catalog-query" type="search" value="${esc(catalogPreview.query)}" placeholder="Nhập mã hoặc tên thủ tục"></label></div><p class="catalog-count">${int(catalogPreview.selected)} thủ tục phù hợp · Chọn bộ lọc không tạo yêu cầu hay trừ credit.</p>${catalogPreview.loading ? `<div class="empty-state"><h2>Đang đọc danh mục…</h2></div>` : catalogPreview.error ? `<p class="collection-error">${esc(catalogPreview.error)}</p>` : `<div class="catalog-list">${rows || '<div class="empty-state">Không tìm thấy TTHC phù hợp.</div>'}</div><div class="catalog-pagination"><span>Hiển thị ${int(first)}–${int(last)} / ${int(catalogPreview.selected)}</span><div><button class="btn small" data-action="catalog-prev" ${catalogPreview.offset === 0 ? "disabled" : ""}>Trang trước</button><button class="btn small" data-action="catalog-next" ${last >= catalogPreview.selected ? "disabled" : ""}>Trang sau</button></div></div>`}<div class="catalog-submit"><div><strong>${catalogPreview.mode === "filtered" ? int(catalogPreview.selected) + " TTHC" : selected ? esc(selected.code) : "Chưa chọn TTHC"}</strong><span title="${esc(selected?.name ?? "")}">${selected ? esc(selected.name) : "Credit sử dụng được hiển thị trước khi xác nhận."}</span></div><button class="btn primary" data-action="submit-statistics" ${canSubmit ? "" : "disabled"}>${paidRequestsEnabled ? "Tra cứu dữ liệu" : "Lấy dữ liệu"}</button></div></section>`;
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
        ? pageLoader()
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
    if (state?.screen === 'overview' && overviewTab === 'analysis')
        bindPaidAnalysis(analysisSelection(), signedInUser?.csrfToken ?? '', render, id => { if (data.groupOrder.includes(id)) {
            overviewTab = 'details';
            state.selectedGroup = id;
            state.selectedMetric = null;
            render();
        } }, (available, reserved) => { if (signedInUser) {
            signedInUser.credits = available;
            signedInUser.reservedCredits = reserved;
        } });
    loadDailyHistory();
    document.querySelectorAll('[data-daily-refresh]').forEach(el => el.addEventListener('click', () => { dailyHistoryCache.delete(dailyContext().key); render(); }));
    document.querySelectorAll('[data-annual-observation]').forEach(el => el.addEventListener('change', () => {
        const context = dailyContext();
        const days = dailyHistoryCache.get(context.key)?.history?.days ?? [];
        if (el.value >= '2026-10-06' && days.some(day => day.reportDate === el.value))
            annualObservationDates.set(context.key, el.value);
        // Native calendar bounds disable pre-launch/future dates; gaps must not select fabricated data.
        render();
    }));
    document.querySelectorAll('[data-group-export]').forEach(button => button.addEventListener('click', () => {
        const group = state.selectedGroup ?? data.groupOrder[0];
        const current = period();
        const query = new URLSearchParams({ root_department_id: data.province.id, period_type: current.type, year: String(current.year), scope: state.scope });
        if (current.value != null)
            query.set('period_value', String(current.value));
        if (state.scope === 'formality')
            query.set('formality_id', data.formality.id);
        openGroupExport({ group, groupLabel: data.groupLabels[group], defaultAll: state.selectedGroup === null, agency: signedInUser?.accessTier === 'agency', query, WorkbookClass: ExcelJS.Workbook,
            context: { name: signedInUser?.accessTier === 'agency' ? unit().name : data.province.name, period: current.label, scope: state.scope === 'all' ? 'Tất cả thủ tục hành chính' : data.formality.code + ' · ' + data.formality.name, snapshot: snapshot() } });
    }));
    if (typeof data !== "undefined" && state?.demo === "normal" && ["overview", "time", "peers"].includes(state.screen)) {
        const snap = snapshot();
        bindComparisonExports({ organization: unit().name, period: period().label, snapshot: snap,
            scope: state.scope === "all" ? "Tất cả thủ tục hành chính" : data.formality.code + " · " + data.formality.name,
            updated: `Điểm: ${dateTime(snap.delivery?.capturedAt)} · Chi tiết: ${dateTime(snap.delivery?.detailsCapturedAt)}` }, () => ExcelJS.Workbook);
    }
    document.querySelectorAll('[data-formula-group]').forEach(button => button.addEventListener("click", () => {
        selectedFormulaGroup = button.dataset.formulaGroup;
        state.screen = "formulas";
        render();
        document.querySelector(`#formula-${selectedFormulaGroup}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }));
    document.querySelectorAll('[data-overview-tab]').forEach(button => {
        const activate = (tab) => {
            overviewTab = tab;
            if (tab === "details") {
                state.selectedGroup = null;
                state.selectedMetric = null;
            }
            render();
            document.querySelector(`[data-overview-tab="${tab}"]`)?.focus({ preventScroll: true });
        };
        button.addEventListener("click", () => activate(button.dataset.overviewTab));
        button.addEventListener("keydown", event => {
            const index = overviewTabItems.findIndex(tab => tab.id === overviewTab);
            const next = event.key === "ArrowRight" ? (index + 1) % 3 : event.key === "ArrowLeft" ? (index + 2) % 3 : event.key === "Home" ? 0 : event.key === "End" ? 2 : null;
            const target = next === null ? null : overviewTabItems[next];
            if (target) {
                event.preventDefault();
                activate(target.id);
            }
        });
    });
    document.querySelectorAll('[data-group-step]').forEach(button => button.addEventListener("click", () => {
        state.selectedGroup = adjacentGroup(data.groupOrder, state.selectedGroup, Number(button.dataset.groupStep));
        state.selectedMetric = null;
        render();
        document.querySelector(`[data-group-step="${button.dataset.groupStep}"]`)?.focus({ preventScroll: true });
    }));
    document.querySelectorAll('[data-action=new-collection]').forEach(el => el.addEventListener('click', () => { void openAcquisition(); }));
    document.querySelectorAll('[data-action=request-history]').forEach(el => el.addEventListener('click', () => { void openAcquisition('history'); }));
    document.querySelectorAll('[data-collection-tab]').forEach(el => el.addEventListener('click', () => { void openAcquisition(el.dataset.collectionTab); }));
    document.querySelector('[data-action=refresh-history]')?.addEventListener('click', () => { void loadMyRequests(); });
    document.querySelector('[data-action=confirm-collection]')?.addEventListener('click', () => { void confirmCollection(); });
    document.querySelector('[data-action=renew-from-collection]')?.addEventListener('click', () => {
        state.modal = "none";
        creditQuote = null;
        render();
        openPersonalCredits((available, reserved) => { if (signedInUser) {
            signedInUser.credits = available;
            signedInUser.reservedCredits = reserved;
            render();
        } });
    });
    document.querySelector('[data-action=open-owned-quote]')?.addEventListener('click', () => {
        if (!creditQuote)
            return;
        const copy = collectionCopy(creditQuote.items);
        state.modal = "none";
        const item = creditQuote.items[0];
        if (copy.mode === "ready" && creditQuote.items.length === 1 && item)
            void openSavedFormality(item);
        else
            void openAcquisition("history");
    });
    document.querySelector('#saved-formality')?.addEventListener('change', event => { const item = library.find(item => item.id === event.target.value); if (item)
        void openSavedFormality(item); });
    document.querySelectorAll('[data-view-request]').forEach(el => el.addEventListener('click', () => {
        const request = myRequests.find(item => item.id === el.dataset.viewRequest);
        if (!request)
            return;
        const selected = data.periods.find(item => item.type === request.periodType && item.year === request.year && (item.value ?? null) === (request.periodValue ?? null));
        if (selected)
            void openSavedFormality({ id: request.formalityId, code: request.code, name: request.name }, selected.id);
    }));
    document.querySelectorAll("[data-trend-toggle]").forEach(button => button.addEventListener("click", () => {
        const id = button.dataset.trendToggle;
        if (hiddenTrendGroups.has(id))
            hiddenTrendGroups.delete(id);
        else
            hiddenTrendGroups.add(id);
        button.setAttribute("aria-pressed", String(!hiddenTrendGroups.has(id)));
        document.querySelectorAll("[data-trend-series]").forEach(series => {
            if (series.dataset.trendSeries === id) {
                if (hiddenTrendGroups.has(id))
                    series.setAttribute("hidden", "");
                else
                    series.removeAttribute("hidden");
            }
        });
    }));
    document.querySelectorAll(".bento-mode #group-detail table").forEach(table => {
        const labels = Array.from(table.querySelectorAll("thead th")).map(th => th.textContent?.trim() ?? "");
        table.querySelectorAll("tbody tr,tfoot tr").forEach(row => {
            let column = 0;
            Array.from(row.cells).forEach(cell => {
                cell.dataset.mobileLabel = labels[column] ?? "";
                column += cell.colSpan;
            });
        });
    });
    document.querySelector("[data-action=open-admin]")?.addEventListener("click", () => {
        if (signedInUser?.role === "admin")
            window.location.assign("/admin.html");
    });
    document.querySelector("[data-action=open-credits]")?.addEventListener("click", () => openPersonalCredits((available, reserved) => { if (signedInUser) {
        signedInUser.credits = available;
        signedInUser.reservedCredits = reserved;
        render();
    } }));
    document.querySelector("[data-action=logout]")?.addEventListener("click", async () => {
        clearPaidAnalysis();
        if (!signedInUser)
            return;
        const response = await fetch("/api/v1/auth/logout", { method: "POST", headers: { "X-QD766-CSRF": signedInUser.csrfToken } });
        if (response.ok)
            window.location.assign("/");
        else
            window.alert("Chưa đăng xuất được. Vui lòng thử lại.");
    });
    document.querySelectorAll("[data-nav]").forEach(el => el.addEventListener("click", () => { const destination = el.dataset.nav; state.screen = destination; if (destination === "overview")
        overviewTab = "overview"; if (destination === "procedure") {
        void openAcquisition();
        return;
    } if (destination === "formulas") {
        render();
    }
    else if (destination === "operations") {
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
    document.querySelectorAll("[data-agency-level]").forEach(el => el.addEventListener("click", () => { agencyLevel = el.dataset.agencyLevel; state.search = ""; render(); }));
    document.querySelectorAll("[data-peer-unit]").forEach(el => el.addEventListener("click", () => {
        const id = el.dataset.peerUnit;
        if (!id || !data.units.some(item => item.departmentId === id) || (signedInUser?.accessTier === "agency" && id !== signedInUser.unitId))
            return;
        state.unitId = id;
        state.screen = "overview";
        state.selectedGroup = el.dataset.peerGroup ?? null;
        state.selectedMetric = null;
        overviewTab = state.selectedGroup ? "details" : "overview";
        saveSelectionUrl();
        render();
        scrollTo(0, 0);
    }));
    document.querySelectorAll("[data-dimension]").forEach(el => el.addEventListener("click", () => { state.peerDimension = el.dataset.dimension; render(); }));
    document.querySelectorAll("[data-group-detail]").forEach(el => el.addEventListener("click", () => { state.selectedGroup = el.dataset.groupDetail; state.selectedMetric = null; overviewTab = "details"; render(); document.querySelector(".overview-tabs")?.scrollIntoView({ behavior: "smooth", block: "start" }); }));
    document.querySelectorAll("[data-metric-detail]").forEach(el => el.addEventListener("click", () => { state.selectedMetric = el.dataset.metricDetail ?? null; render(); document.querySelector(".comparison-card")?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }));
    document.querySelector("[data-action=clear-metric-detail]")?.addEventListener("click", () => { state.selectedMetric = null; render(); });
    document.querySelector("[data-action=close-group-detail]")?.addEventListener("click", () => { state.selectedGroup = null; state.selectedMetric = null; render(); document.querySelector("#group-detail")?.scrollIntoView({ behavior: "smooth", block: "start" }); });
    document.querySelector("#province-select")?.addEventListener("change", e => { void switchProvince(e.target.value); });
    document.querySelector("#unit-select")?.addEventListener("change", e => { state.unitId = e.target.value; state.selectedGroup = null; state.selectedMetric = null; saveSelectionUrl(); render(); });
    document.querySelector("#period-type")?.addEventListener("change", e => { const type = e.target.value; const currentYear = period().year; const matches = data.periods.filter(item => item.type === type && item.year === currentYear); const fallback = data.periods.filter(item => item.type === type); const match = latestPeriod(matches) ?? latestPeriod(fallback); if (match)
        void selectPeriod(match.id); });
    document.querySelector("#period-value")?.addEventListener("change", e => { void selectPeriod(e.target.value); });
    document.querySelector("#report-year")?.addEventListener("change", e => { const year = Number(e.target.value); const matches = data.periods.filter(item => item.type === period().type && item.year === year); const match = latestPeriod(matches); if (match)
        void selectPeriod(match.id); });
    document.querySelector("#scope-select")?.addEventListener("change", e => { completionMessage = ""; state.scope = e.target.value; state.selectedGroup = null; state.selectedMetric = null; if (state.scope === "formality") {
        data.formality = { id: "", code: "", name: "" };
        catalogPreview.selectedId = null;
        state.demo = "ready";
        render();
        void loadLibrary();
    }
    else {
        void loadSelection().then(() => loadProvinceBenchmarks());
    } saveSelectionUrl(); });
    document.querySelector("#catalog-level")?.addEventListener("change", e => { catalogPreview.level = e.target.value; catalogPreview.selectedId = null; catalogPreview.offset = 0; void loadCatalogPreview(); });
    document.querySelector("#catalog-field")?.addEventListener("change", e => { catalogPreview.field = e.target.value; catalogPreview.selectedId = null; catalogPreview.offset = 0; void loadCatalogPreview(); });
    document.querySelector("#catalog-query")?.addEventListener("input", e => { catalogPreview.query = e.target.value; catalogPreview.selectedId = null; catalogPreview.offset = 0; window.clearTimeout(catalogSearchTimer); catalogSearchTimer = window.setTimeout(() => { void loadCatalogPreview(); }, 350); });
    document.querySelectorAll("input[name=catalog-formality]").forEach(el => el.addEventListener("change", () => { const item = catalogPreview.items.find(candidate => candidate.id === el.value); if (!item)
        return; catalogPreview.selectedId = item.id; render(); }));
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
    document.querySelectorAll("[data-action=submit-statistics]").forEach(el => el.addEventListener("click", () => { void prepareCollection(); }));
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
    saveSelectionUrl();
    if (state.screen === "procedure") {
        await loadLibrary();
        if (collectionTab === "new")
            await loadCatalogPreview();
        else
            await loadMyRequests();
        return;
    }
    if (state.scope === "formality") {
        data.formality = { id: "", code: "", name: "" };
        catalogPreview.selectedId = null;
        saveSelectionUrl();
        state.demo = "ready";
        render();
        await loadLibrary();
    }
    else {
        await loadSelection();
    }
    void loadProvinceBenchmarks();
}
async function loadProvinceBenchmarks() {
    if (paidRequestsEnabled && state.scope === "formality")
        return;
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
function announceCollectionComplete(label) {
    completionMessage = `${label}: dữ liệu đã được lưu và sẵn sàng để xem.`;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => { completionMessage = ""; render(); }, 6000);
    if ("Notification" in window && Notification.permission === "granted")
        new Notification("QD766 · Lấy dữ liệu hoàn tất", { body: completionMessage });
}
async function requestCollection(requestId) {
    if (publicReadOnly || state.scope !== "formality" || !data.formality.id)
        throw new Error("Chỉ cho phép lấy dữ liệu theo TTHC.");
    const selected = period(), requestedKey = selectionKey(), label = collectionLabel();
    const requestBody = { periodType: selected.type, year: selected.year, periodValue: selected.value ?? null, scope: "formality", provinceCode: catalogProvinceCode(), formalityId: data.formality.id, formalityCode: data.formality.code };
    const response = await fetch("/api/v1/dashboard/requests", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(requestBody) });
    if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(typeof problem.detail === "string" ? problem.detail : `HTTP ${response.status}`);
    }
    const result = await response.json();
    if (result.state === "ready") {
        announceCollectionComplete(label);
        if (requestedKey === selectionKey()) {
            delete data.snapshots[snapshotKey(selected.id, "formality", data.formality.id)];
            await loadSelection();
        }
        else
            render();
        return;
    }
    if (requestId === selectionRequest && requestedKey === selectionKey()) {
        pendingMessage = result.message;
        state.demo = result.circuitState === "open" ? "blocked" : "queued";
    }
    if (result.jobId)
        collectionTracker.track({ id: result.jobId, kind: "job", key: requestedKey, label, state: result.circuitState === "open" ? "blocked" : "queued", message: result.message });
    else
        render();
}
async function submitStatistics() {
    if (publicReadOnly || submittingCollection || collectionTracker.hasActive(selectionKey()) || catalogPreview.loading || catalogPreview.error || state.scope !== "formality")
        return;
    if (catalogPreview.mode === "filtered" ? !catalogPreview.selected : !catalogPreview.selectedId)
        return;
    submittingCollection = true;
    const requestId = ++selectionRequest;
    completionMessage = "";
    pendingMessage = "Đang gửi yêu cầu lấy dữ liệu...";
    state.demo = "loading";
    render();
    try {
        if (catalogPreview.mode === "filtered")
            await requestFilteredBatch(requestId);
        else
            await requestCollection(requestId);
    }
    catch (error) {
        if (requestId !== selectionRequest)
            return;
        pendingMessage = error instanceof Error ? error.message : String(error);
        state.demo = "error";
    }
    finally {
        submittingCollection = false;
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
async function requestFilteredBatch(requestId) {
    const selected = period(), requestedKey = selectionKey(), label = collectionLabel();
    const payload = { provinceCode: catalogProvinceCode(), periodType: selected.type, year: selected.year, periodValue: selected.value ?? null, includeInternal: true };
    if (catalogPreview.level)
        payload.level = catalogPreview.level;
    if (catalogPreview.field)
        payload.field = catalogPreview.field;
    if (catalogPreview.query.trim())
        payload.query = catalogPreview.query.trim();
    const response = await fetch("/api/v1/formality-batches", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) {
        const problem = await response.json().catch(() => ({}));
        throw new Error(typeof problem.detail === "string" ? problem.detail : `HTTP ${response.status}`);
    }
    const batch = await response.json();
    if (batch.state === "succeeded") {
        announceCollectionComplete(label);
        if (requestedKey === selectionKey()) {
            state.demo = "ready";
            await loadCatalogPreview();
        }
        else
            render();
        return;
    }
    const message = `Yêu cầu gồm ${int(batch.totalItems)} TTHC đã được lưu; sẽ thông báo khi xử lý xong.`;
    if (requestId === selectionRequest && requestedKey === selectionKey()) {
        pendingMessage = message;
        state.demo = "queued";
    }
    collectionTracker.track({ id: batch.id, kind: "batch", key: requestedKey, label, state: batch.state, message });
}
async function loadCatalogPreview() {
    const requestId = ++catalogPreviewRequest;
    const selected = period();
    catalogPreview.loading = true;
    catalogPreview.error = null;
    if (state.screen === "procedure")
        render();
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
    if (state.screen === "procedure" || (state.scope === "formality" && state.demo === "ready"))
        render();
}
async function loadSelection() {
    const requestId = ++selectionRequest;
    const selected = period();
    const key = snapshotKey(selected.id, state.scope, data.formality.id);
    if (data.snapshots[key] && data.snapshots[key].detailsLoaded !== false) {
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
    let loaded = recentDashboards.get(rootDepartmentId);
    if (!loaded) {
        const response = await fetch(`/api/v1/dashboard?fast=true&compact=true&root_department_id=${encodeURIComponent(rootDepartmentId)}`);
        if (!response.ok)
            throw new Error(`HTTP ${response.status}`);
        loaded = normalizeLoadedData(await response.json());
        recentDashboards.set(rootDepartmentId, loaded);
    }
    if (requestId !== selectionRequest)
        return;
    const initialPeriod = initialPeriodFor(loaded);
    if (!initialPeriod)
        throw new Error("Tỉnh/thành phố chưa có kỳ báo cáo hoàn chỉnh");
    data = loaded;
    pendingProvinceId = "";
    document.title = "Hệ thống phân tích Bộ chỉ số 766";
    catalogPreview = { loading: false, error: null, level: "", field: "", query: "", fields: [], selected: 0, available: 0, missing: 0, items: [], selectedId: null, offset: 0, mode: "single" };
    state = { ...state, periodId: initialPeriod.id, scope: "all", unitId: data.defaultUnitId, selectedGroup: null, selectedMetric: null, search: "", demo: "normal", modal: "none" };
    saveSelectionUrl();
    void loadLibrary();
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
    // Clean before API calls, including pending-account and error/empty screens.
    // Session authentication stays in its HttpOnly cookie, never in URL parameters.
    const cleanSearch = cleanLoginSearch(location.search);
    if (cleanSearch !== null)
        history.replaceState(history.state ?? null, "", `${location.pathname}${cleanSearch}${location.hash ?? ""}`);
    const productionSite = document.querySelector('meta[name="qd766-deployment"]')?.getAttribute("content") === "public";
    let invitationOnly = false;
    try {
        const registrationToken = new URLSearchParams(location.hash.slice(1)).get("register");
        if (registrationToken) {
            history.replaceState(history.state ?? null, "", `${location.pathname}${location.search}`);
            const accepted = await fetch("/api/v1/auth/registration-link", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: registrationToken }) });
            if (!accepted.ok)
                throw new Error("Link đăng ký đã hết hạn, đã đủ số người hoặc đã thu hồi.");
            location.assign("/api/v1/auth/google/start");
            return;
        }
        const invitation = new URLSearchParams(location.hash.slice(1)).get("invite");
        if (invitation) {
            history.replaceState(history.state ?? null, "", `${location.pathname}${location.search}`);
            const accepted = await fetch("/api/v1/auth/invite", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: invitation }) });
            if (!accepted.ok)
                throw new Error("Lời mời đã hết hạn, đã dùng hoặc đã được thu hồi. Hãy liên hệ quản trị viên.");
            location.assign("/api/v1/auth/google/start");
            return;
        }
        const policyResponse = await fetch("/api/v1/access-policy");
        if (productionSite && !policyResponse.ok)
            throw new Error("Website chưa kết nối được backend HTTPS máy cơ quan.");
        if (policyResponse.ok) {
            const policy = await policyResponse.json();
            localSimulation = Boolean(policy.localSimulation);
            localGoogleTrial = Boolean(policy.localGoogleTrial);
            invitationOnly = Boolean(policy.inviteRequired);
            if (productionSite && policy.publicReadOnly !== true)
                throw new Error("Backend chưa bật chế độ truy cập công khai an toàn.");
            publicReadOnly = Boolean(policy.publicReadOnly);
            loginRequired = Boolean(policy.loginRequired);
            googleLoginEnabled = Boolean(policy.googleLoginEnabled);
            paidRequestsEnabled = Boolean(policy.paidRequestsEnabled);
            geminiAnalysisEnabled = Boolean(policy.geminiAnalysisEnabled);
        }
        if (googleLoginEnabled || loginRequired) {
            const meResponse = await fetch("/api/v1/auth/me");
            if (meResponse.ok)
                signedInUser = await meResponse.json();
            else if (meResponse.status !== 401 && meResponse.status !== 403)
                throw new Error("Chưa kiểm tra được phiên đăng nhập. Vui lòng thử lại.");
            if (loginRequired && (!signedInUser || (!signedInUser.provinceId && signedInUser.role !== "admin"))) {
                if (await mountTrialRegistration(root, localGoogleTrial))
                    return;
                if (localSimulation) {
                    location.assign("/local-trial.html");
                    return;
                }
                root.innerHTML = loginView({ pending: Boolean(signedInUser), name: signedInUser?.name ?? "", local: localGoogleTrial,
                    failed: new URLSearchParams(location.search).get("login") === "failed",
                    inviteRequired: invitationOnly, googleEnabled: googleLoginEnabled });
                bind();
                return;
            }
        }
        const remembered = typeof location !== "undefined" ? new URLSearchParams(location.search) : new URLSearchParams();
        const rememberedProvince = remembered.get("province");
        const dashboardUrl = rememberedProvince ? `/api/v1/dashboard?fast=true&compact=true&root_department_id=${encodeURIComponent(rememberedProvince)}` : "/api/v1/dashboard?fast=true&compact=true";
        const [apiResponse, provincesResponse] = await Promise.all([fetch(dashboardUrl), fetch("/api/v1/dashboard/provinces")]);
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
        recentDashboards.set(data.province.id, data);
        if (!initialPeriod)
            throw new Error("Chưa có kỳ báo cáo ban đầu hoàn chỉnh");
        state = { screen: "overview", periodId: initialPeriod.id, scope: "all", unitId: data.defaultUnitId, peerDimension: "total", selectedGroup: null, selectedMetric: null, search: "", demo: "normal", modal: "none" };
        const rememberedPeriod = data.periods.find(item => item.id === remembered.get("period"));
        if (rememberedPeriod)
            state.periodId = rememberedPeriod.id;
        const rememberedUnit = remembered.get("unit");
        if (rememberedUnit && data.units.some(item => item.departmentId === rememberedUnit))
            state.unitId = rememberedUnit;
        if (data.snapshots[snapshotKey(state.periodId, "all", "")]?.detailsLoaded === false)
            await loadSelection();
        document.title = "Hệ thống phân tích Bộ chỉ số 766";
        render();
        if (paidRequestsEnabled || canAcquire()) {
            await loadLibrary();
            if (remembered.get("scope") === "formality") {
                const saved = library.find(item => item.id === remembered.get("formality"));
                if (saved)
                    await openSavedFormality(saved);
                else {
                    state.scope = "formality";
                    state.demo = "ready";
                    render();
                }
            }
        }
        if (paidRequestsEnabled)
            void loadMyRequests();
        void loadProvinceBenchmarks();
    }
    catch (error) {
        root.innerHTML = `<main class="content"><div class="empty-state"><h2>Không thể tải dữ liệu</h2><p>${esc(error instanceof Error ? error.message : error)}</p><p>${productionSite ? "Vui lòng thử lại sau hoặc liên hệ quản trị viên. Website không sử dụng dữ liệu mẫu thay cho dữ liệu thật." : "Hãy kiểm tra máy chủ cục bộ và dữ liệu đầu vào."}</p></div></main>`;
    }
    finally {
        root.setAttribute("aria-busy", "false");
    }
}
void start();
//# sourceMappingURL=app.js.map