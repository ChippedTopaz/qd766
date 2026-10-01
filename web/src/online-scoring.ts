import type { Entity } from "./types.js";

export const ONLINE_SCORING_PROFILE = {
  id: "qd766-online-v1",
  label: "Công thức phân tích v1",
  tolerance: 0.015,
  components: [
    {
      id: "online-provision",
      name: "Tỷ lệ TTHC cung cấp dịch vụ công trực tuyến",
      numeratorKeys: ["partialCount", "fullCount"],
      denominatorKey: "authorityCount",
      targetPercent: 80,
      maxScore: 2,
    },
    {
      id: "online-service-used",
      name: "Tỷ lệ dịch vụ công trực tuyến có phát sinh hồ sơ",
      numeratorKeys: ["onlineDossierCount"],
      denominatorKey: "onlineServiceTotal",
      targetPercent: 100,
      maxScore: 4,
    },
    {
      id: "online-submission",
      name: "Tỷ lệ hồ sơ nộp trực tuyến",
      numeratorKeys: ["channelOnlineSum"],
      denominatorKey: "channelTotalSum",
      targetPercent: 50,
      maxScore: 6,
    },
  ],
  declaredIndicators: [
    { scope: "Tỉnh", name: "Tỷ lệ cung cấp dịch vụ công trực tuyến toàn trình trên tổng số thủ tục hành chính đủ điều kiện", dataStatus: "Chỉ tiêu nghiệp vụ bổ sung; chưa có dòng riêng trong METRICS đang lưu" },
    { scope: "Tỉnh", name: "Tỷ lệ hồ sơ dịch vụ công trực tuyến toàn trình trên tổng số hồ sơ TTHC đủ điều kiện cung cấp toàn trình", dataStatus: "Nguồn METRICS khai báo 12 điểm; response chưa trả tử số, mẫu số riêng" },
    { scope: "Tỉnh, xã", name: "Tỷ lệ TTHC thuộc phạm vi quản lý cung cấp dịch vụ công trực tuyến", dataStatus: "Chưa khai báo điểm tối đa riêng; có số liệu tổng hợp để phân tích" },
    { scope: "Tỉnh", name: "Tỷ lệ TTHC thuộc phạm vi quản lý được cung cấp dịch vụ công trực tuyến chủ động, phân loại theo từng mức độ", dataStatus: "Chưa khai báo điểm tối đa riêng và chưa có tử số, mẫu số riêng" },
    { scope: "Tỉnh", name: "Tỷ lệ hồ sơ dịch vụ công chủ động, phân loại theo từng mức độ", dataStatus: "Chưa khai báo điểm tối đa riêng và chưa có tử số, mẫu số riêng" },
    { scope: "Tỉnh, xã", name: "Tỷ lệ hồ sơ theo hình thức nộp", dataStatus: "Chưa khai báo điểm tối đa riêng; có số liệu trực tuyến, trực tiếp và bưu chính" },
  ],
} as const;

export interface OnlineScoreComponent {
  id: string;
  name: string;
  numerator: number;
  denominator: number;
  ratio: number;
  targetPercent: number;
  score: number;
  maxScore: number;
  missingScore: number;
}

export interface OnlineScoreAnalysis {
  profileId: string;
  profileLabel: string;
  components: OnlineScoreComponent[];
  calculatedScore: number;
  apiScore: number | null;
  difference: number | null;
  matchesApi: boolean | null;
}

function numeric(parameters: Record<string, unknown>, key: string): number | null {
  const value = parameters[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function analyzeOnlineScore(entity: Entity): OnlineScoreAnalysis | null {
  const components: OnlineScoreComponent[] = [];
  for (const definition of ONLINE_SCORING_PROFILE.components) {
    const numeratorValues = definition.numeratorKeys.map((key) => numeric(entity.parameters, key));
    const denominator = numeric(entity.parameters, definition.denominatorKey);
    if (numeratorValues.some((value) => value === null) || denominator === null || denominator <= 0) return null;
    const numerator = numeratorValues.reduce<number>((sum, value) => sum + (value ?? 0), 0);
    const ratio = numerator / denominator * 100;
    const score = Math.min(definition.maxScore, definition.maxScore * ratio / definition.targetPercent);
    components.push({
      id: definition.id,
      name: definition.name,
      numerator,
      denominator,
      ratio,
      targetPercent: definition.targetPercent,
      score,
      maxScore: definition.maxScore,
      missingScore: Math.max(0, definition.maxScore - score),
    });
  }
  const calculatedScore = components.reduce((sum, component) => sum + component.score, 0);
  const difference = entity.apiScore === null ? null : calculatedScore - entity.apiScore;
  return {
    profileId: ONLINE_SCORING_PROFILE.id,
    profileLabel: ONLINE_SCORING_PROFILE.label,
    components,
    calculatedScore,
    apiScore: entity.apiScore,
    difference,
    matchesApi: difference === null ? null : Math.abs(difference) <= ONLINE_SCORING_PROFILE.tolerance,
  };
}
