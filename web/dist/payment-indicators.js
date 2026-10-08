/** Display-only reconciliation approved against DVCQG charts on 08/10/2026.
 * Never replaces the authoritative API group score. */
export const paymentDefinitions = [
    { id: '3.5', name: 'Tỷ lệ TTHC có yêu cầu nghĩa vụ tài chính được cung cấp trên Cổng DVCQG', numerator: 'totalFeeDossierFormality', denominator: 'totalFeeFormality', maximum: 2, target: 80 },
    { id: '3.5b', name: 'Tỷ lệ TTHC có giao dịch thanh toán trực tuyến', numerator: 'totalDossierOnlineFormalityPaymentSuccess', denominator: 'totalFeeDossierFormalityDistinct', maximum: 2, target: 80 },
    { id: '3.6', name: 'Tỷ lệ hồ sơ thanh toán trực tuyến', numerator: 'totalDossierOnlinePaymentSuccess', denominator: 'totalDossierFinancialObligation', maximum: 6, target: 100 },
];
export function paymentIndicators(parameters) {
    return paymentDefinitions.map(d => {
        const number = (key) => { const v = parameters[key]; return typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : null; };
        const numerator = number(d.numerator), denominator = number(d.denominator);
        const ratio = numerator !== null && denominator !== null && denominator > 0 && numerator <= denominator ? numerator / denominator * 100 : null;
        const score = ratio === null ? null : Math.round((Math.min(d.maximum, ratio / d.target * d.maximum) + Number.EPSILON) * 100) / 100;
        return { ...d, numerator, denominator, ratio, score, lost: score === null ? null : Math.round((d.maximum - score) * 100) / 100 };
    });
}
export function paymentRows(parameters) {
    const num = (v, digits = 2) => v === null ? '—' : v.toLocaleString('vi-VN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    return paymentIndicators(parameters).map(d => `<tr><td>${d.name}</td><td class="num">${num(d.numerator, 0)}</td><td class="num">${num(d.denominator, 0)}</td><td class="num">${d.ratio === null ? '—' : num(d.ratio) + '%'}</td><td class="num">${num(d.score)}</td><td class="num">${num(d.maximum)}</td><td class="num lost">${num(d.lost)}</td></tr>`);
}
//# sourceMappingURL=payment-indicators.js.map