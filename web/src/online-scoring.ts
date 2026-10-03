import type { Entity } from './types.js';

export const ONLINE_SCORING_PROFILE = {
  id:'qd766-online-reference-20261003',
  label:'Chờ xác nhận phân bổ điểm và ánh xạ tham số',
  enabled:false,
} as const;

// Retain the consumer contract, but never publish the retired 2–4–6 hypothesis
// as an official score or improvement recommendation.
export interface OnlineScoreComponent {
  id:string; name:string; numerator:number; denominator:number; ratio:number;
  targetPercent:number; score:number; maxScore:number; missingScore:number;
}
export interface OnlineScoreAnalysis {
  profileId:string; profileLabel:string; components:OnlineScoreComponent[];
  calculatedScore:number; apiScore:number|null; difference:number|null; matchesApi:boolean|null;
}
export function analyzeOnlineScore(_entity:Entity):OnlineScoreAnalysis|null {
  // Reference 3.3 also requires synchronization and electronic-result eligibility.
  // Missing maxima/mapping must not become zero or guessed component scores.
  return null;
}
