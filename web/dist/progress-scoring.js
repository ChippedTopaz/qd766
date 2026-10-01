export const PROGRESS_SCORING_PROFILE = {
    id: "qd766-progress-v1",
    label: "Tỷ lệ hồ sơ giải quyết đúng hạn",
    tolerance: 0.015,
};
function numeric(parameters, key) {
    const value = parameters[key];
    return typeof value === "number" && Number.isFinite(value) ? value : null;
}
export function analyzeProgressScore(entity) {
    const totalReceived = numeric(entity.parameters, "totalReceived");
    const totalOnTime = numeric(entity.parameters, "totalOnTime");
    const explicitOverdue = numeric(entity.parameters, "totalOverdue");
    const maxScore = entity.apiMaxScore;
    if (totalReceived === null || totalOnTime === null || maxScore === null)
        return null;
    const overdueDerived = explicitOverdue === null;
    const totalOverdue = explicitOverdue ?? Math.max(0, totalReceived - totalOnTime);
    const onTimeRatio = totalReceived > 0 ? totalOnTime / totalReceived * 100 : null;
    const overdueRatio = totalReceived > 0 ? totalOverdue / totalReceived * 100 : null;
    const calculatedScore = onTimeRatio === null ? null : onTimeRatio / 100 * maxScore;
    const missingScore = calculatedScore === null ? null : Math.max(0, maxScore - calculatedScore);
    const difference = calculatedScore === null || entity.apiScore === null
        ? null
        : calculatedScore - entity.apiScore;
    return {
        profileId: PROGRESS_SCORING_PROFILE.id,
        profileLabel: PROGRESS_SCORING_PROFILE.label,
        totalReceived,
        totalOnTime,
        totalOverdue,
        overdueDerived,
        averageProcessingDays: numeric(entity.parameters, "avgProcessingDays"),
        onTimeRatio,
        overdueRatio,
        calculatedScore,
        maxScore,
        missingScore,
        apiScore: entity.apiScore,
        difference,
        matchesApi: difference === null ? null : Math.abs(difference) <= PROGRESS_SCORING_PROFILE.tolerance,
    };
}
//# sourceMappingURL=progress-scoring.js.map