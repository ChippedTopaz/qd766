const GROUP_META = {
  transparency: { icon: "01", color: "#0d6b4f" },
  "dvc-progress-tree": { icon: "02", color: "#39756c" },
  "provide-online-tree": { icon: "03", color: "#30739a" },
  "dossier-digitized": { icon: "04", color: "#765d9d" },
  "handling-satisfaction": { icon: "05", color: "#b26d36" },
  "formality-online-payment-tree": { icon: "06", color: "#a94e48" },
};

const PARAMETER_LABELS = {
  totalReceived: "Hồ sơ đã tiếp nhận",
  totalOnTime: "Hồ sơ xử lý đúng hạn",
  totalCompleted: "Hồ sơ đã hoàn thành",
  avgProcessingDays: "Số ngày xử lý trung bình",
  authorityCount: "Tổng số TTHC thuộc thẩm quyền",
  partialCount: "Dịch vụ công trực tuyến một phần",
  fullCount: "Dịch vụ công trực tuyến toàn trình",
  onlineDossierCount: "Hồ sơ nộp trực tuyến",
  onlineServiceTotal: "Tổng hồ sơ của dịch vụ trực tuyến",
  channelOnlineSum: "Hồ sơ qua kênh trực tuyến",
  channelDirectSum: "Hồ sơ nộp trực tiếp",
  channelPostalSum: "Hồ sơ qua bưu chính",
  channelTotalSum: "Tổng hồ sơ theo kênh",
  onlineOnTimeSum: "Hồ sơ trực tuyến đúng hạn",
  onlineOverdueSum: "Hồ sơ trực tuyến quá hạn",
  totalDossierOnlinePaymentSuccess: "Hồ sơ thanh toán trực tuyến thành công",
  totalDossierFinancialObligation: "Hồ sơ có nghĩa vụ tài chính",
  totalDossierOnlineFormalityPaymentSuccess: "Hồ sơ TTHC thanh toán trực tuyến",
  totalFeeDossierFormalityDistinct: "TTHC phát sinh hồ sơ có phí",
  totalFeeDossierFormality: "Hồ sơ thuộc TTHC có phí",
  totalFeeFormality: "Tổng TTHC có phí",
  scoreDelta: "Chênh lệch điểm",
  averageScore: "Điểm trung bình",
};

const state = {
  data: null,
  periodId: "month-2026-08",
  scope: "all",
  group: "transparency",
  tab: "indicators",
  search: "",
};

const $ = (selector) => document.querySelector(selector);
const numberFormat = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function displayNumber(value, fallback = "—") {
  return value === null || value === undefined ? fallback : numberFormat.format(value);
}

function currentSnapshot() {
  return state.data.snapshots[`${state.periodId}:${state.scope}`];
}

function currentDataset() {
  return currentSnapshot().datasets.find((item) => item.group === state.group);
}

function groupRatio(dataset) {
  if (!dataset || !dataset.root.apiMaxScore) return 0;
  return Math.max(0, Math.min(100, (dataset.root.apiScore / dataset.root.apiMaxScore) * 100));
}

function periodLabel() {
  return state.data.periods.find((period) => period.id === state.periodId)?.label ?? "";
}

function renderSummary() {
  const snapshot = currentSnapshot();
  const score = snapshot.provinceAggregatedScore;
  const max = snapshot.provinceAggregatedMaximum;
  const ratio = max ? (score / max) * 100 : 0;
  $("#total-score").textContent = displayNumber(score);
  $("#total-max").textContent = `/ ${displayNumber(max)} điểm`;
  $("#score-percent").textContent = displayNumber(ratio);
  $("#score-ring").style.setProperty("--score-angle", `${ratio * 3.6}deg`);
  const scopeText = state.scope === "all" ? "Toàn bộ thủ tục hành chính" : "TTHC 2.000815";
  $("#period-summary").textContent = `${periodLabel()} · ${scopeText}`;
}

function renderCards() {
  const snapshot = currentSnapshot();
  const byGroup = Object.fromEntries(snapshot.datasets.map((item) => [item.group, item]));
  if (!byGroup[state.group]) state.group = snapshot.datasets[0].group;
  $("#group-cards").innerHTML = state.data.groupOrder.map((group) => {
    const dataset = byGroup[group];
    const meta = GROUP_META[group];
    const active = group === state.group;
    if (!dataset) {
      return `
        <button class="group-card unavailable" style="--accent:${meta.color}" disabled>
          <div class="card-top"><span class="group-icon">${meta.icon}</span><span class="status-pill">Không hỗ trợ</span></div>
          <h3>${escapeHtml(state.data.groupLabels[group])}</h3>
          <p class="card-status">Không có drill-down theo thủ tục hành chính</p>
        </button>`;
    }
    const ratio = groupRatio(dataset);
    return `
      <button class="group-card ${active ? "active" : ""}" data-group="${group}" style="--accent:${meta.color};--progress:${ratio}%" aria-pressed="${active}">
        <div class="card-top"><span class="group-icon">${meta.icon}</span><span class="status-pill">Điểm API</span></div>
        <h3>${escapeHtml(dataset.label)}</h3>
        <div class="card-score"><strong>${displayNumber(dataset.root.apiScore)}</strong><span>/ ${displayNumber(dataset.root.apiMaxScore)} điểm</span></div>
        <div class="mini-bar"><span></span></div>
      </button>`;
  }).join("");
  document.querySelectorAll("[data-group]").forEach((button) => {
    button.addEventListener("click", () => {
      state.group = button.dataset.group;
      state.search = "";
      $("#unit-search").value = "";
      render();
      $("#detail-section").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function renderMetrics(metrics) {
  if (!metrics.length) return '<div class="empty-state">Nhóm này không trả metric code riêng.</div>';
  return `<div class="metric-list">${metrics.map((metric) => {
    const quality = metric.extras?.dataQualityMessage;
    return `
      <article class="metric-item">
        <div class="metric-head">
          <h3>${escapeHtml(metric.name)}</h3>
          <span class="metric-points">${displayNumber(metric.apiScore)} / ${displayNumber(metric.apiMaxScore)}</span>
        </div>
        <div class="metric-values">
          <div><span>Tử số</span><strong>${displayNumber(metric.numerator)}</strong></div>
          <div><span>Mẫu số</span><strong>${displayNumber(metric.denominator)}</strong></div>
          <div><span>Tỷ lệ</span><strong>${displayNumber(metric.ratio)}${metric.ratio == null ? "" : "%"}</strong></div>
        </div>
        ${quality ? `<div class="quality-note"><strong>Dữ liệu cần lưu ý:</strong> ${escapeHtml(quality)}</div>` : ""}
      </article>`;
  }).join("")}</div>`;
}

function renderParameters(parameters) {
  const entries = Object.entries(parameters).filter(([, value]) => value !== null && value !== undefined);
  if (!entries.length) return "";
  return `
    <p class="parameter-intro">Các parameters dưới đây được hiển thị nguyên giá trị API để phục vụ phân tích. Website không dùng chúng để ghi đè điểm.</p>
    <div class="parameter-grid">${entries.map(([key, value]) => `
      <div class="parameter-item"><span>${escapeHtml(PARAMETER_LABELS[key] ?? key)}</span><strong>${typeof value === "number" ? displayNumber(value) : escapeHtml(value)}</strong></div>
    `).join("")}</div>`;
}

function formulaMessage(dataset) {
  if (dataset.group === "provide-online-tree") {
    return "Chưa xác định công thức tính điểm Dịch vụ công trực tuyến. Các parameters được giữ để xem và phân tích; điểm hiển thị là điểm API.";
  }
  if (dataset.schemaKind === "parameters") {
    return "Nhóm này trả parameters trực tiếp. Giao diện hiển thị điểm API và toàn bộ dữ liệu thành phần, không tự tính lại điểm.";
  }
  return "";
}

function renderIndicators(dataset) {
  const metrics = renderMetrics(dataset.root.metrics);
  const parameters = renderParameters(dataset.root.parameters);
  $("#indicator-content").innerHTML = `${metrics}${parameters}`;
  const message = formulaMessage(dataset);
  const note = $("#formula-note");
  note.hidden = !message;
  note.innerHTML = message ? `<strong>Trạng thái công thức:</strong> ${escapeHtml(message)}` : "";
}

function levelLabel(entity) {
  if (entity.departmentLevel === "COMMUNE") return "Cấp xã";
  if (entity.departmentType === "PROVINCIAL_DEPARTMENT") return "Cơ quan tỉnh";
  if (entity.departmentLevel === "PROVINCE") return "Cấp tỉnh";
  return entity.departmentLevel || entity.departmentType || "—";
}

function renderUnits(dataset) {
  const query = state.search.trim().toLocaleLowerCase("vi");
  const rows = dataset.children.filter((entity) => !query || entity.departmentName.toLocaleLowerCase("vi").includes(query));
  $("#unit-count").textContent = `${numberFormat.format(rows.length)} / ${numberFormat.format(dataset.children.length)} đơn vị`;
  $("#unit-rows").innerHTML = rows.slice(0, 200).map((entity) => {
    const ratio = entity.apiMaxScore ? Math.max(0, Math.min(100, entity.apiScore / entity.apiMaxScore * 100)) : 0;
    return `<tr>
      <td class="unit-name">${escapeHtml(entity.departmentName)}</td>
      <td><span class="level-chip">${escapeHtml(levelLabel(entity))}</span></td>
      <td><strong>${displayNumber(entity.apiScore)} / ${displayNumber(entity.apiMaxScore)}</strong></td>
      <td>${displayNumber(entity.apiRatio)}${entity.apiRatio == null ? "" : "%"}</td>
      <td><div class="row-bar"><span><i style="width:${ratio}%"></i></span><b>${displayNumber(ratio)}%</b></div></td>
    </tr>`;
  }).join("") || '<tr><td colspan="5" class="empty-state">Không tìm thấy đơn vị phù hợp.</td></tr>';
}

function renderDetail() {
  const dataset = currentDataset();
  $("#detail-title").textContent = dataset.label;
  $("#detail-score").innerHTML = `<strong>${displayNumber(dataset.root.apiScore)} / ${displayNumber(dataset.root.apiMaxScore)}</strong>${displayNumber(dataset.root.apiRatio)}% · nguồn DVCQG`;
  $("#raw-reference").textContent = `Raw fixture: ${dataset.raw.path} · SHA-256 ${dataset.raw.sha256.slice(0, 12)}…`;
  renderIndicators(dataset);
  renderUnits(dataset);
}

function renderTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    const active = tab.dataset.tab === state.tab;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `${state.tab}-panel`);
  });
}

function render() {
  renderSummary();
  renderCards();
  renderDetail();
  renderTabs();
}

function bindControls() {
  const period = $("#period-select");
  period.innerHTML = state.data.periods.map((item) => `<option value="${item.id}">${escapeHtml(item.label)}</option>`).join("");
  period.value = state.periodId;
  period.addEventListener("change", (event) => {
    state.periodId = event.target.value;
    state.search = "";
    $("#unit-search").value = "";
    render();
  });
  const formalityOption = $("#scope-select option[value='formality']");
  formalityOption.textContent = `${state.data.formality.code} · ${state.data.formality.name}`;
  $("#scope-select").addEventListener("change", (event) => {
    state.scope = event.target.value;
    state.search = "";
    $("#unit-search").value = "";
    render();
  });
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      state.tab = tab.dataset.tab;
      renderTabs();
    });
  });
  $("#unit-search").addEventListener("input", (event) => {
    state.search = event.target.value;
    renderUnits(currentDataset());
  });
}

async function start() {
  try {
    const apiBase = window.QD766_API_BASE || "http://127.0.0.1:8767";
    let response;
    let sourceLabel = "PostgreSQL nội bộ · dữ liệu đã xác minh";
    let usingApi = true;
    try {
      response = await fetch(`${apiBase}/api/v1/dashboard`);
      if (!response.ok) throw new Error(`API HTTP ${response.status}`);
    } catch (apiError) {
      console.warn("Không thể đọc PostgreSQL API; dùng snapshot tĩnh.", apiError);
      response = await fetch("./data/snapshots.json");
      sourceLabel = "Snapshot tĩnh dự phòng";
      usingApi = false;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    if (usingApi) {
      try {
        const statusResponse = await fetch(`${apiBase}/api/v1/system-status`);
        if (statusResponse.ok) {
          const systemStatus = await statusResponse.json();
          if (systemStatus.circuitState === "open") {
            sourceLabel = "PostgreSQL nội bộ · DVCQG tạm dừng · dữ liệu đã lưu";
            document.querySelector(".source-badge").classList.add("warning");
          }
        }
      } catch (statusError) {
        console.warn("Không đọc được trạng thái hệ thống.", statusError);
      }
    }
    if (!state.data.snapshots[`${state.periodId}:${state.scope}`]) {
      state.periodId = state.data.periods[0]?.id;
    }
    $("#source-label").textContent = sourceLabel;
    bindControls();
    render();
  } catch (error) {
    console.error(error);
    $("#error-state").hidden = false;
  }
}

start();
