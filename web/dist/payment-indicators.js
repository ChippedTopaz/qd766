/** Display-only reconciliation approved against DVCQG charts on 08/10/2026.
 * Never replaces the authoritative API group score. */
export const paymentDefinitions = [
    { id: '3.5', name: 'Tỷ lệ TTHC có yêu cầu nghĩa vụ tài chính được cung cấp trên Cổng DVCQG', numerator: 'totalFeeDossierFormality', denominator: 'totalFeeFormality', maximum: 2, target: 80 },
    { id: '3.5b', name: 'Tỷ lệ TTHC có giao dịch thanh toán trực tuyến', numerator: 'totalDossierOnlineFormalityPaymentSuccess', denominator: 'totalFeeDossierFormalityDistinct', maximum: 2, target: 80 },
    { id: '3.6', name: 'Tỷ lệ hồ sơ thanh toán trực tuyến', numerator: 'totalDossierOnlinePaymentSuccess', denominator: 'totalDossierFinancialObligation', maximum: 6, target: 100 },
];
export function paymentIndicators(parameters, scope = 'all') {
    return paymentDefinitions.map(d => {
        const number = (key) => { const v = parameters[key]; return typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : null; };
        const notApplicable = scope === 'formality' && d.id !== '3.6';
        const numerator = number(notApplicable ? (d.id === '3.5' ? 'agencyPaymentProvidedNumerator' : 'agencyPaymentTransactionsNumerator') : d.numerator), denominator = number(notApplicable ? (d.id === '3.5' ? 'agencyPaymentProvidedDenominator' : 'agencyPaymentTransactionsDenominator') : d.denominator);
        const ratio = numerator !== null && denominator !== null && denominator > 0 && numerator <= denominator ? numerator / denominator * 100 : null;
        const score = ratio === null ? null : Math.round((Math.min(d.maximum, ratio / d.target * d.maximum) + Number.EPSILON) * 100) / 100;
        return { ...d, numerator: notApplicable ? null : numerator, denominator: notApplicable ? null : denominator, ratio: notApplicable ? null : ratio, notApplicable, score, lost: score === null ? null : Math.round((d.maximum - score) * 100) / 100 };
    });
}
export function paymentComparisonPoint(entity, key, scope = 'all') {
    const definition = paymentDefinitions.find(d => 'payment:' + d.id === key);
    if (!definition)
        return null;
    const projected = entity.comparisonPoints?.[key];
    if (projected && Number.isFinite(projected.score))
        return { label: definition.name, score: projected.score, maximum: projected.maximum };
    const indicator = paymentIndicators(entity.parameters, scope).find(d => d.id === definition.id);
    return indicator?.score == null ? null : { label: definition.name, score: indicator.score, maximum: indicator.maximum };
}
export function paymentRows(parameters, scope = 'all', selected = null) {
    const num = (v, digits = 2) => v === null ? '—' : v.toLocaleString('vi-VN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    return paymentIndicators(parameters, scope).map(d => `<tr${d.score === null ? '' : ` class="selectable-row ${selected === 'payment:' + d.id ? 'selected' : ''}" data-metric-detail="payment:${d.id}"`}><td>${d.score === null ? d.name : `<button type="button" class="row-link">${d.name}</button>`}</td><td class="num">${d.notApplicable ? 'N/A' : num(d.numerator, 0)}</td><td class="num">${d.notApplicable ? 'N/A' : num(d.denominator, 0)}</td><td class="num">${d.notApplicable ? 'N/A' : d.ratio === null ? '—' : num(d.ratio) + '%'}</td><td class="num">${num(d.score)}</td><td class="num">${num(d.maximum)}</td><td class="num lost">${num(d.lost)}</td></tr>`);
}
//# sourceMappingURL=payment-indicators.js.map