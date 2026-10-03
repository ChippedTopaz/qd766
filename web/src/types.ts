export type Scope = "all" | "formality";
export type ScreenId = "overview" | "time" | "peers" | "procedure" | "suggestions" | "quality" | "operations" | "formulas";
export type GroupId =
  | "transparency"
  | "dvc-progress-tree"
  | "provide-online-tree"
  | "dossier-digitized"
  | "handling-satisfaction"
  | "formality-online-payment-tree";

export interface PeriodOption {
  id: string;
  label: string;
  type: "month" | "quarter" | "year";
  year: number;
  value?: number | null;
  provisional: boolean;
}

export interface Metric {
  code: string;
  name: string;
  numerator: number | null;
  denominator: number | null;
  ratio: number | null;
  apiScore: number | null;
  apiMaxScore: number | null;
  extras: Record<string, unknown>;
}

export interface Entity {
  departmentId: string;
  departmentName: string;
  departmentType: string | null;
  departmentLevel: string | null;
  agencyLevel: string | null;
  apiScore: number | null;
  apiMaxScore: number | null;
  apiRatio: number | null;
  scoreSource: "dvcqg-api" | "dvcqg-national-summary";
  metrics: Metric[];
  parameters: Record<string, unknown>;
}

export interface CaptureInfo {
  capturedAt: string;
  httpStatus: number;
  contentType: string;
  bytes: number;
}

export interface Dataset {
  group: GroupId;
  label: string;
  schemaKind: "metrics" | "parameters";
  formulaStatus: string;
  scorePolicy: "api-authoritative";
  root: Entity;
  children: Entity[];
  raw: { path: string; sha256: string };
  capture: CaptureInfo;
}

export interface Snapshot {
  scope: Scope;
  formalityId: string | null;
  status: {
    state: "complete" | "incomplete";
    requiredGroups: GroupId[];
    loadedGroups: GroupId[];
    unsupportedGroups: GroupId[];
    missingGroups: GroupId[];
  };
  provinceAggregatedScore: number | null;
  provinceAggregatedMaximum: number | null;
  scorePolicy: Record<string, unknown>;
  datasets: Dataset[];
  delivery?: {
    result?: string;
    capturedAt?: string;
    detailsCapturedAt?: string | null;
    detailsAvailable?: boolean;
    provisional?: boolean;
    stale?: boolean;
    summaryStale?: boolean;
    detailsStale?: boolean;
    message?: string;
  };
}

export interface UnitOption {
  departmentId: string;
  departmentName: string;
  departmentType: string | null;
  departmentLevel: string | null;
}

export interface AppData {
  schemaVersion: number;
  source: string;
  province: { id: string; name: string; code?: string | null };
  formality: { id: string; code: string; name: string };
  metricCatalog: Array<{
    stt: number;
    scope: string;
    group: string;
    name: string;
    metricCode: string | null;
    responseName: string | null;
    maxScore: number | null;
    formulaDescription: string;
    apiUrl: string;
    sourceRow: number;
    applicableToCommune: boolean;
  }>;
  defaultUnitId: string;
  units: UnitOption[];
  periods: PeriodOption[];
  groupOrder: GroupId[];
  groupLabels: Record<GroupId, string>;
  snapshots: Record<string, Snapshot>;
}

export type ValueState =
  | { kind: "VALID_NUMBER"; value: number }
  | { kind: "ZERO_VALUE"; value: 0 }
  | { kind: "NO_DATA_NULL"; value: null }
  | { kind: "NOT_APPLICABLE_MAX"; value: number; maximum: number }
  | { kind: "UNSUPPORTED_SOURCE"; value: null; reason: string };

export interface PeerStats {
  rank: number;
  total: number;
  tiedCount: number;
  percentile: number;
  mean: number;
  median: number;
  p75: number;
  gapToMedian: number;
  gapToP75: number;
}

export interface UnitGroupView {
  id: GroupId;
  label: string;
  entity: Entity | null;
  score: ValueState;
  maximum: number | null;
  ratio: number | null;
  peer: PeerStats | null;
  dataset: Dataset | null;
}

export interface UnitView {
  id: string;
  name: string;
  totalScore: number | null;
  totalMaximum: number | null;
  ratio: number | null;
  peer: PeerStats | null;
  groups: UnitGroupView[];
  volume: number | null;
}

export interface Suggestion {
  id: string;
  severity: "critical" | "warning" | "positive" | "info";
  category: "gap" | "saturation" | "quality" | "formula" | "strength";
  groupId: GroupId | null;
  finding: string;
  evidence: string;
  impact: string;
  action: string;
  confidence: "Cao" | "Trung bình" | "Thấp";
  deepLink: ScreenId;
}
