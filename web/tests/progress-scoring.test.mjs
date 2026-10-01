import assert from "node:assert/strict";

import { analyzeProgressScore } from "../dist/progress-scoring.js";

const baseEntity = {
  apiScore: 17.54,
  apiMaxScore: 20,
  parameters: {
    totalReceived: 358643,
    totalOnTime: 314557,
    avgProcessingDays: 2.91,
  },
};

{
  const result = analyzeProgressScore(baseEntity);
  assert.ok(result);
  assert.equal(result.totalOverdue, 44086);
  assert.equal(result.overdueDerived, true);
  assert.ok(Math.abs(result.onTimeRatio - 87.70755319356574) < 1e-9);
  assert.ok(Math.abs(result.calculatedScore - 17.54151063871315) < 1e-9);
  assert.equal(result.matchesApi, true);
}

{
  const result = analyzeProgressScore({
    ...baseEntity,
    apiScore: 0,
    parameters: {
      totalReceived: 0,
      totalOnTime: 0,
      totalOverdue: 0,
      avgProcessingDays: 0,
    },
  });
  assert.ok(result);
  assert.equal(result.totalOverdue, 0);
  assert.equal(result.overdueDerived, false);
  assert.equal(result.onTimeRatio, null);
  assert.equal(result.calculatedScore, null);
  assert.equal(result.averageProcessingDays, 0);
}

console.log("PROGRESS_SCORING_OK");
