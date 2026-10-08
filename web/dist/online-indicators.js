export function onlineIndicators(parameters) {
    const get = (key) => typeof parameters[key] === 'number' && Number.isFinite(parameters[key]) && parameters[key] >= 0 ? parameters[key] : null;
    const sum = (...values) => values.every(v => v !== null) ? values.reduce((a, v) => a + v, 0) : null;
    const authority = get('authorityCount'), partial = get('partialCount'), full = get('fullCount');
    const direct = get('channelDirectSum'), postal = get('channelPostalSum'), total = get('channelTotalSum');
    const onTime = get('onlineOnTimeSum'), overdue = get('onlineOverdueSum'), processed = sum(onTime, overdue);
    const remaining = authority !== null && partial !== null && full !== null ? authority - partial - full : null;
    const row = (name, formula, numerator, denominator) => ({ name, formula, numerator, denominator,
        ratio: numerator !== null && denominator !== null && denominator > 0 && numerator >= 0 && numerator <= denominator ? numerator / denominator * 100 : null });
    return [
        row('TTHC cung cấp DVCTT một phần', 'Một phần / TTHC thuộc phạm vi × 100%', partial, authority),
        row('TTHC cung cấp DVCTT toàn trình', 'Toàn trình / TTHC thuộc phạm vi × 100%', full, authority),
        row('TTHC còn lại', '(TTHC thuộc phạm vi − một phần − toàn trình) / TTHC thuộc phạm vi × 100%', remaining, authority),
        row('Hồ sơ nộp trực tuyến', 'Hồ sơ nộp trực tuyến / tổng hồ sơ theo hình thức nộp × 100%', get('channelOnlineSum'), total),
        row('Hồ sơ nộp trực tiếp và bưu chính', '(Hồ sơ trực tiếp + bưu chính) / tổng hồ sơ theo hình thức nộp × 100%', sum(direct, postal), total),
        row('Hồ sơ trực tuyến xử lý đúng hạn', 'Đúng hạn / (đúng hạn + quá hạn) × 100%', onTime, processed),
        row('Hồ sơ trực tuyến xử lý quá hạn', 'Quá hạn / (đúng hạn + quá hạn) × 100%', overdue, processed),
        row('DVCTT có phát sinh hồ sơ nộp trực tuyến trong kỳ', 'DVC có phát sinh hồ sơ trực tuyến / tổng DVCTT × 100%', get('onlineDossierCount'), get('onlineServiceTotal')),
    ].filter(r => r.numerator !== null || r.denominator !== null);
}
//# sourceMappingURL=online-indicators.js.map