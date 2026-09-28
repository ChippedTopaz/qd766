import type {
  AppData,
  Dataset,
  Entity,
  GroupId,
  PeerStats,
  Scope,
  Snapshot,
  Suggestion,
  UnitGroupView,
  UnitView,
  ValueState,
} from "./types.js";

const EPSILON = 0.005;

export function snapshotFor(data: AppData, periodId: string, scope: Scope): Snapshot {
  const snapshot = data.snapshots[`${periodId}:${scope}`];
  if (!snapshot) throw new Error(`Không tìm thấy snapshot ${periodId}/${scope}`);
  return snapshot;
}

function entityFor(dataset: Dataset, unitId: string): Entity | null {
  if (dataset.root.departmentId === unitId) return dataset.root;
  return dataset.children.find((entity) => entity.departmentId === unitId) ?? null;
}

function comparableEntities(dataset: Dataset, departmentLevel: string | null): Entity[] {
  return dataset.children.filter(
    (entity) => entity.departmentLevel === departmentLevel && entity.apiScore !== null,
  );
}

export function numericState(value: number | null): ValueState {
  if (value === null) return { kind: "NO_DATA_NULL", value: null };
  if (value === 0) return { kind: "ZERO_VALUE", value: 0 };
  return { kind: "VALID_NUMBER", value };
}

export function mean(values: number[]): number {
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
}

export function quantile(values: number[], q: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const position = (sorted.length - 1) * q;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  const lowValue = sorted[lower] ?? 0;
  const highValue = sorted[upper] ?? lowValue;
  return lowValue + (highValue - lowValue) * (position - lower);
}

export function peerStats(values: number[], current: number): PeerStats | null {
  const valid = values.filter(Number.isFinite);
  if (!valid.length) return null;
  const rank = 1 + valid.filter((value) => value > current + EPSILON).length;
  const tiedCount = valid.filter((value) => Math.abs(value - current) <= EPSILON).length;
  const percentile = valid.length === 1 ? 100 : ((valid.length - rank) / (valid.length - 1)) * 100;
  const median = quantile(valid, 0.5);
  const p75 = quantile(valid, 0.75);
  return {
    rank,
    total: valid.length,
    tiedCount,
    percentile,
    mean: mean(valid),
    median,
    p75,
    gapToMedian: current - median,
    gapToP75: current - p75,
  };
}

function unitTotal(snapshot: Snapshot, unitId: string): { score: number | null; maximum: number | null } {
  const entities = snapshot.datasets.map((dataset) => entityFor(dataset, unitId));
  if (entities.some((entity) => entity === null || entity.apiScore === null || entity.apiMaxScore === null)) {
    return { score: null, maximum: null };
  }
  return {
    score: Number(entities.reduce((sum, entity) => sum + (entity?.apiScore ?? 0), 0).toFixed(2)),
    maximum: Number(entities.reduce((sum, entity) => sum + (entity?.apiMaxScore ?? 0), 0).toFixed(2)),
  };
}

export function allUnitTotals(snapshot: Snapshot, departmentLevel = "COMMUNE"): Array<{ id: string; name: string; score: number; maximum: number; ratio: number; volume: number }> {
  const first = snapshot.datasets[0];
  if (!first) return [];
  const progress = snapshot.datasets.find((dataset) => dataset.group === "dvc-progress-tree");
  return first.children
    .filter((entity) => entity.departmentLevel === departmentLevel)
    .flatMap((entity) => {
      const total = unitTotal(snapshot, entity.departmentId);
      if (total.score === null || total.maximum === null || total.maximum === 0) return [];
      const progressEntity = progress ? entityFor(progress, entity.departmentId) : null;
      const rawVolume = progressEntity?.parameters["totalReceived"];
      return [{
        id: entity.departmentId,
        name: entity.departmentName,
        score: total.score,
        maximum: total.maximum,
        ratio: (total.score / total.maximum) * 100,
        volume: typeof rawVolume === "number" ? rawVolume : 0,
      }];
    });
}

export function buildUnitView(data: AppData, periodId: string, scope: Scope, unitId: string): UnitView {
  const snapshot = snapshotFor(data, periodId, scope);
  const unit = data.units.find((option) => option.departmentId === unitId);
  if (!unit) throw new Error(`Không tìm thấy đơn vị ${unitId}`);
  const groups: UnitGroupView[] = data.groupOrder.map((groupId) => {
    const dataset = snapshot.datasets.find((item) => item.group === groupId) ?? null;
    if (!dataset) {
      return {
        id: groupId,
        label: data.groupLabels[groupId],
        entity: null,
        score: {
          kind: "UNSUPPORTED_SOURCE",
          value: null,
          reason: groupId === "handling-satisfaction"
            ? "Cổng DVCQG không hỗ trợ phân tách Mức độ hài lòng theo từng TTHC."
            : "Nguồn dữ liệu chưa hỗ trợ.",
        },
        maximum: null,
        ratio: null,
        peer: null,
        dataset: null,
      };
    }
    const entity = entityFor(dataset, unitId);
    const score = entity?.apiScore ?? null;
    const peerValues = unit.departmentLevel === "PROVINCE_TOTAL" ? [] : comparableEntities(dataset, unit.departmentLevel).flatMap((peer) => peer.apiScore === null ? [] : [peer.apiScore]);
    return {
      id: groupId,
      label: dataset.label,
      entity,
      score: numericState(score),
      maximum: entity?.apiMaxScore ?? null,
      ratio: entity?.apiRatio ?? null,
      peer: score === null ? null : peerStats(peerValues, score),
      dataset,
    };
  });
  const total = unitTotal(snapshot, unitId);
  const totals = unit.departmentLevel === "PROVINCE_TOTAL" ? [] : allUnitTotals(snapshot, unit.departmentLevel ?? "COMMUNE");
  const currentTotal = totals.find((item) => item.id === unitId);
  const progress = groups.find((group) => group.id === "dvc-progress-tree")?.entity;
  const volumeValue = progress?.parameters["totalReceived"];
  return {
    id: unitId,
    name: unit.departmentName,
    totalScore: total.score,
    totalMaximum: total.maximum,
    ratio: total.score !== null && total.maximum ? (total.score / total.maximum) * 100 : null,
    peer: currentTotal ? peerStats(totals.map((item) => item.score), currentTotal.score) : null,
    groups,
    volume: typeof volumeValue === "number" ? volumeValue : null,
  };
}

export function similarVolumePeers(snapshot: Snapshot, unitId: string, limit = 5) {
  const level = snapshot.datasets[0]?.children.find((item) => item.departmentId === unitId)?.departmentLevel ?? "COMMUNE";
  const totals = allUnitTotals(snapshot, level ?? "COMMUNE");
  const current = totals.find((item) => item.id === unitId);
  if (!current) return [];
  return totals
    .filter((item) => item.id !== unitId)
    .sort((a, b) => Math.abs(a.volume - current.volume) - Math.abs(b.volume - current.volume))
    .slice(0, limit);
}

export function immediatePeers(snapshot: Snapshot, unitId: string, radius = 3) {
  const level = snapshot.datasets[0]?.children.find((item) => item.departmentId === unitId)?.departmentLevel ?? "COMMUNE";
  const ranked = allUnitTotals(snapshot, level ?? "COMMUNE").sort((a, b) => b.score - a.score || a.name.localeCompare(b.name, "vi"));
  const index = ranked.findIndex((item) => item.id === unitId);
  if (index < 0) return [];
  return ranked.slice(Math.max(0, index - radius), Math.min(ranked.length, index + radius + 1));
}

const ACTIONS: Partial<Record<GroupId, string>> = {
  transparency: "Rà soát hồ sơ đồng bộ và danh mục TTHC phải công bố, ưu tiên các bản ghi có cảnh báo chất lượng.",
  "dvc-progress-tree": "Kiểm tra các hồ sơ sắp quá hạn và phân công xử lý theo thời hạn còn lại.",
  "dossier-digitized": "Ưu tiên số hóa kết quả và tái sử dụng dữ liệu ở các TTHC có khối lượng hồ sơ lớn.",
  "handling-satisfaction": "Kiểm tra phản ánh kiến nghị và quy trình tiếp nhận, trả kết quả tại Bộ phận Một cửa.",
  "formality-online-payment-tree": "Rà soát TTHC có nghĩa vụ tài chính nhưng chưa phát sinh thanh toán trực tuyến thành công.",
};

export function buildSuggestions(unit: UnitView): Suggestion[] {
  const suggestions: Suggestion[] = [];
  for (const group of unit.groups) {
    if (!group.entity || group.entity.apiScore === null || group.entity.apiMaxScore === null || !group.peer) continue;
    const ratio = group.entity.apiMaxScore ? group.entity.apiScore / group.entity.apiMaxScore : 0;
    if (ratio >= 0.95) {
      suggestions.push({
        id: `${group.id}-saturation`, severity: "positive", category: "saturation", groupId: group.id,
        finding: `${group.label} đã gần mức điểm tối đa`,
        evidence: `${group.entity.apiScore.toFixed(2)}/${group.entity.apiMaxScore.toFixed(2)} điểm, đạt ${(ratio * 100).toFixed(1)}%.`,
        impact: `Dư địa còn ${(group.entity.apiMaxScore - group.entity.apiScore).toFixed(2)} điểm.`,
        action: "Duy trì quy trình hiện tại và chuyển ưu tiên sang nhóm còn nhiều dư địa hơn.",
        confidence: "Cao", deepLink: "overview",
      });
    } else if (group.peer.gapToMedian < -1) {
      suggestions.push({
        id: `${group.id}-gap`, severity: group.peer.gapToMedian < -3 ? "critical" : "warning", category: "gap", groupId: group.id,
        finding: `${group.label} thấp hơn trung vị tỉnh`,
        evidence: `${group.entity.apiScore.toFixed(2)} điểm; trung vị ${group.peer.median.toFixed(2)}; chênh ${group.peer.gapToMedian.toFixed(2)} điểm.`,
        impact: `Còn ${(group.entity.apiMaxScore - group.entity.apiScore).toFixed(2)} điểm chưa đạt trong nhóm này.`,
        action: ACTIONS[group.id] ?? "Mở các số liệu nghiệp vụ thành phần để xác định nguyên nhân trước khi lập kế hoạch xử lý.",
        confidence: group.id === "provide-online-tree" ? "Thấp" : "Trung bình", deepLink: "overview",
      });
    } else if (group.peer.percentile >= 75) {
      suggestions.push({
        id: `${group.id}-strength`, severity: "positive", category: "strength", groupId: group.id,
        finding: `${group.label} thuộc nhóm kết quả tốt của tỉnh`,
        evidence: `Phân vị P${Math.round(group.peer.percentile)}, hạng ${group.peer.rank}/${group.peer.total}.`,
        impact: "Đây là kết quả tốt cần duy trì để tránh mất điểm ở kỳ sau.",
        action: "Chuẩn hóa cách làm hiện tại và theo dõi các chỉ báo đầu vào ở mỗi kỳ.",
        confidence: "Cao", deepLink: "peers",
      });
    }
    for (const metric of group.entity.metrics) {
      if (metric.denominator !== null && metric.denominator > 0 && metric.denominator <= 3) {
        suggestions.push({
          id: `${group.id}-${metric.code}-small`, severity: "warning", category: "quality", groupId: group.id,
          finding: `${metric.name} có mẫu số quá nhỏ`,
          evidence: `${metric.numerator ?? "—"}/${metric.denominator} hồ sơ; tỷ lệ có thể biến động mạnh chỉ với một hồ sơ.`,
          impact: "Không nên kết luận xu hướng chỉ từ tỷ lệ phần trăm của kỳ này.",
          action: "Kiểm tra dữ liệu hồ sơ gốc và theo dõi thêm kỳ tiếp theo.",
          confidence: "Cao", deepLink: "quality",
        });
      }
    }
  }
  suggestions.push({
    id: "online-formula", severity: "info", category: "formula", groupId: "provide-online-tree",
    finding: "Công thức Dịch vụ công trực tuyến đang chờ chuẩn hóa",
    evidence: "Hệ thống nguồn đã công bố điểm và số liệu thành phần nhưng chưa đủ căn cứ xác định trọng số chi tiết.",
    impact: "Không thể ước lượng điểm tăng thêm từ từng parameter một cách đáng tin cậy.",
    action: "Dùng điểm đã công bố làm chuẩn; chỉ phân tích hướng tăng hoặc giảm của các số liệu thành phần.",
    confidence: "Thấp", deepLink: "quality",
  });
  const order = { critical: 0, warning: 1, positive: 2, info: 3 } as const;
  return suggestions.sort((a, b) => order[a.severity] - order[b.severity]);
}
