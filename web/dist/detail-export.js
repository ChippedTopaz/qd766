import { parameterLabels } from './parameter-labels.js';
import { detailMetricName, orderSatisfactionRows } from './satisfaction-display-order.js';
import { paymentIndicators } from './payment-indicators.js';
import { onlineIndicators } from './online-indicators.js';
import { analyzeProgressScore } from './progress-scoring.js';
const metric = (code, name, numerator, denominator, ratio, score, maximum) => ({ code, name, numerator, denominator, ratio, apiScore: score, apiMaxScore: maximum, extras: {} });
/** Read-only presentation projection; caller still owns authentication and scope. */
export function detailExportEntries(group, entity, scope) {
    const derived = (m) => ({ key: m.code, kind: 'metric', metric: m, derived: true });
    if (group === 'formality-online-payment-tree')
        return paymentIndicators(entity.parameters).map(d => derived(metric(d.id, d.name, d.numerator, d.denominator, d.ratio, d.score, d.maximum)));
    if (group === 'provide-online-tree')
        return onlineIndicators(entity.parameters).map((d, i) => derived(metric('online:' + i, d.name, d.numerator, d.denominator, d.ratio, null, null)));
    if (group === 'dvc-progress-tree') {
        const a = analyzeProgressScore(entity);
        if (a) {
            const entries = [
                derived(metric('totalOnTime', 'Hồ sơ giải quyết đúng hạn', a.totalOnTime, a.totalReceived, a.onTimeRatio, a.apiScore, a.maxScore)),
                derived(metric('totalOverdue', 'Hồ sơ quá hạn giải quyết', a.totalOverdue, a.totalReceived, a.overdueRatio, null, null)),
                { key: 'totalReceived', kind: 'parameter', name: 'Tổng hồ sơ tiếp nhận', value: a.totalReceived },
            ];
            if (scope === 'formality' && a.averageProcessingDays !== null)
                entries.push({ key: 'avgProcessingDays', kind: 'parameter', name: 'Thời gian giải quyết trung bình (ngày)', value: a.averageProcessingDays });
            return entries;
        }
    }
    const entries = entity.metrics.filter(m => m.code !== 'scoreDelta').map(m => ({ key: m.code, kind: 'metric', metric: { ...m, name: detailMetricName(group, m) }, derived: false }));
    for (const [key, value] of Object.entries(entity.parameters))
        if (parameterLabels[key] && !(group === 'dvc-progress-tree' && scope === 'all' && key === 'avgProcessingDays'))
            entries.push({ key, kind: 'parameter', name: parameterLabels[key], value });
    return orderSatisfactionRows(group, entries);
}
//# sourceMappingURL=detail-export.js.map