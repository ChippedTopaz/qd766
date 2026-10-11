import { formulaMaximums } from './formula-maximums.js';
import { getFormulaConfiguration } from './formula-reference.js';
import { loadFormulaConfiguration } from './formula-loader.js';
import { paymentDefinitions } from './payment-indicators.js';
import { detailMetricName, orderSatisfactionRows } from './satisfaction-display-order.js';
const valid = (v) => typeof v === 'number' && Number.isFinite(v) && v >= 0;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v) => v.toLocaleString('vi-VN', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
export function simulationMetrics(group, entity) {
    const formulas = getFormulaConfiguration().groups.find(g => g.id === group)?.items ?? [];
    const result = [];
    const add = (id, name, a, b, sourceScore) => {
        const f = formulas.find(f => f.id === id);
        // Do not infer a scoring rule from source maximums or simulate compound expressions.
        if (!f || !valid(f.maximum) || f.maximum <= 0 || !valid(a) || !valid(b) || a > b || !Number.isSafeInteger(a) || !Number.isSafeInteger(b))
            return;
        if (b === 0 && !(group === 'transparency' && (id === '1.1' || id === '1.2')))
            return;
        // 5.4 supplies its resulting satisfaction ratio as numerator/denominator in
        // the API; its reference expression is a complement rather than a fraction.
        if ((f.multiplier ?? '× 100%').replace(/\s/g, '') !== '×100%' && !(group === 'handling-satisfaction' && id === '5.4'))
            return;
        const target = f.target ?? 100;
        if (!valid(target) || target <= 0 || target > 100)
            return;
        const growthMode = (group === 'dossier-digitized' && id === '4.5a') || (group === 'formality-online-payment-tree' && (id === '3.5' || id === '3.5b')) ? 'numerator-only' : 'both';
        result.push({ id, name, numerator: a, denominator: b, maximum: f.maximum, target, sourceScore, growthMode });
    };
    if (group === 'dvc-progress-tree')
        add('2.1', 'Hồ sơ giải quyết đúng hạn', entity.parameters.totalOnTime, entity.parameters.totalReceived, entity.apiScore);
    else if (group === 'formality-online-payment-tree')
        for (const p of paymentDefinitions)
            add(p.id, p.name, entity.parameters[p.numerator], entity.parameters[p.denominator], null);
    else
        for (const { metric: m } of orderSatisfactionRows(group, entity.metrics.map(metric => ({ key: metric.code, metric })))) {
            const id = formulaMaximums[group].find(f => f.metricCode === m.code)?.formulaId;
            if (id && m.apiMaxScore !== 0)
                add(id, detailMetricName(group, m), m.numerator, m.denominator, m.apiScore);
        }
    return result;
}
export function simulatedScore(m, extra) {
    if (!Number.isSafeInteger(extra) || extra < 0 || !Number.isSafeInteger(m.numerator + extra) || !Number.isSafeInteger(m.denominator + (m.growthMode === 'numerator-only' ? 0 : extra)))
        throw new Error('Nhập số lượng tăng thêm là số nguyên không âm trong giới hạn cho phép.');
    const a = m.numerator + extra, b = m.denominator + (m.growthMode === 'numerator-only' ? 0 : extra);
    if (m.growthMode === 'numerator-only' && a > b)
        throw new Error('Số lượng đạt không được vượt tổng số. Chỉ có thể tăng thêm tối đa ' + (m.denominator - m.numerator).toLocaleString('vi-VN') + '.');
    if (b === 0)
        return { numerator: a, denominator: b, ratio: null, score: null };
    const ratio = a / b * 100;
    return { numerator: a, denominator: b, ratio, score: Math.min(m.maximum, ratio / m.target * m.maximum) };
}
export function requiredGrowth(m, desired) {
    if (!Number.isFinite(desired) || desired < 0 || desired > m.maximum)
        return { extra: null, message: 'Điểm mong muốn phải từ 0 đến ' + fmt(m.maximum) + '.' };
    const current = simulatedScore(m, 0).score;
    if (desired === 0 || (current !== null && desired <= current))
        return { extra: 0, message: '' };
    if (m.denominator === 0)
        return m.growthMode === 'numerator-only' ? { extra: null, message: 'Mẫu số bằng 0 và được giữ nguyên nên chưa thể giả lập điểm.' } : { extra: 1, message: '' };
    const r = desired / m.maximum * m.target / 100;
    if (m.growthMode !== 'numerator-only' && r >= 1 && m.numerator < m.denominator)
        return { extra: null, message: 'Không thể đạt tuyệt đối ' + fmt(m.maximum) + ' điểm bằng cách chỉ thêm hồ sơ đạt: đã có ' + (m.denominator - m.numerator) + ' hồ sơ không đạt. Điểm có thể tiến gần ' + fmt(m.maximum) + ' nhưng luôn thấp hơn mức này, dù làm tròn có thể hiển thị bằng điểm tối đa.' };
    let extra = Math.max(0, Math.ceil((r * m.denominator - m.numerator) / (m.growthMode === 'numerator-only' ? 1 : 1 - r) - 1e-9));
    if (!Number.isSafeInteger(extra) || !Number.isSafeInteger(extra + m.denominator))
        return { extra: null, message: 'Số hồ sơ cần thêm vượt giới hạn tính toán an toàn.' };
    // Compare unrounded scores; never claim a threshold is met from display rounding.
    while (extra > 0 && simulatedScore(m, extra - 1).score >= desired)
        extra--;
    if (simulatedScore(m, extra).score < desired)
        extra++;
    return { extra, message: '' };
}
export async function openScoreSimulator(group, label, entity) {
    if (document.querySelector('.score-simulator'))
        return;
    const trigger = document.activeElement, dialog = document.createElement('dialog');
    dialog.className = 'score-simulator';
    dialog.setAttribute('aria-label', 'Giả lập điểm số');
    dialog.innerHTML = '<div class="panel-head"><h2>Giả lập điểm số</h2><button type="button" class="btn" data-sim-close>Đóng</button></div><div class="panel-body" data-sim-body>Đang tải Công thức tính…</div>';
    document.body.append(dialog);
    dialog.showModal();
    dialog.querySelector('[data-sim-close]')?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { dialog.remove(); if (trigger?.isConnected)
        trigger.focus(); }, { once: true });
    const body = dialog.querySelector('[data-sim-body]');
    try {
        await loadFormulaConfiguration();
    }
    catch {
        body.textContent = 'Không tải được Công thức tính đang lưu. Vui lòng đóng và thử lại.';
        return;
    }
    if (!dialog.isConnected)
        return;
    const metrics = simulationMetrics(group, entity);
    if (!metrics.length) {
        body.textContent = 'Nhóm này chưa có chỉ tiêu đủ số liệu tử số, mẫu số và công thức chấm điểm để giả lập. Không suy diễn điểm từ dữ liệu thiếu.';
        return;
    }
    body.innerHTML = `<p>${esc(label)} · Chỉ tính thử, không thay đổi dữ liệu thật.</p><label><strong>Chỉ tiêu</strong><select data-sim-metric>${metrics.map((m, i) => `<option value="${i}">${esc(m.name)}</option>`).join('')}</select></label><div data-sim-baseline></div><p data-sim-growth-note></p><div class="sim-inputs"><label><strong>Số lượng đạt tăng thêm</strong><input type="number" inputmode="numeric" min="0" step="1" value="0" data-sim-extra></label><label><strong>Điểm ghi nhận muốn đạt</strong><input type="number" inputmode="decimal" min="0" step="any" data-sim-desired></label></div><div data-sim-result role="status" aria-live="polite"></div>`;
    let selected = metrics[0];
    const extra = body.querySelector('[data-sim-extra]'), desired = body.querySelector('[data-sim-desired]');
    const output = body.querySelector('[data-sim-result]');
    const render = (count) => {
        try {
            const now = simulatedScore(selected, 0), next = simulatedScore(selected, count);
            output.innerHTML = `<dl><dt>Số lượng đạt / Tổng số</dt><dd>${next.numerator.toLocaleString('vi-VN')} / ${next.denominator.toLocaleString('vi-VN')}</dd><dt>Tỷ lệ giả lập</dt><dd>${next.ratio === null ? '—' : fmt(next.ratio) + '%'}</dd><dt class="sim-green">Điểm giả lập</dt><dd class="sim-green">${next.score === null ? '—' : fmt(next.score)} / ${fmt(selected.maximum)}</dd><dt class="sim-green">Điểm tăng theo công thức</dt><dd class="sim-green">${next.score === null || now.score === null ? '—' : '+' + fmt(next.score - now.score)}</dd><dt>Hồ sơ đạt cần thêm</dt><dd>${count.toLocaleString('vi-VN')}</dd></dl>`;
            if (selected.denominator === 0)
                output.innerHTML += '<p>Hiện tại 0/0 chưa tính được tỷ lệ. Thêm 1 hồ sơ đạt sẽ thành 1/1, đạt điểm tối đa. Không quy đổi 0/0 thành điểm 0.</p>';
            if (selected.growthMode !== 'numerator-only' && selected.target === 100 && selected.numerator < selected.denominator)
                output.innerHTML += '<p>' + esc(requiredGrowth(selected, selected.maximum).message) + '</p>';
        }
        catch (e) {
            output.textContent = e.message;
        }
    };
    const reset = () => {
        extra.value = '0';
        desired.value = '';
        desired.max = String(selected.maximum);
        if (selected.growthMode === 'numerator-only')
            extra.max = String(selected.denominator - selected.numerator);
        else
            extra.removeAttribute('max');
        body.querySelector('[data-sim-growth-note]').textContent = selected.growthMode === 'numerator-only' ? 'Số lượng đạt tăng thêm chỉ cộng vào tử số; tổng số giữ nguyên.' : 'Mỗi hồ sơ đạt tăng thêm được cộng vào cả số lượng đạt và tổng số.';
        const initialScore = simulatedScore(selected, 0).score;
        body.querySelector('[data-sim-baseline]').innerHTML = `<p><strong>Hiện tại:</strong> ${selected.numerator.toLocaleString('vi-VN')}/${selected.denominator.toLocaleString('vi-VN')} · Điểm theo công thức: ${initialScore === null ? '—' : fmt(initialScore)} · Điểm nguồn: ${selected.sourceScore === null ? '—' : fmt(selected.sourceScore)}</p><p><strong>Cách tính:</strong> Tỷ lệ / ${selected.target}% × ${fmt(selected.maximum)}; tối đa ${fmt(selected.maximum)} điểm.</p>`;
        render(0);
    };
    const metricSelect = body.querySelector('[data-sim-metric]');
    metricSelect.title = selected.name;
    metricSelect.addEventListener('change', e => { selected = metrics[Number(e.target.value)]; metricSelect.title = selected.name; reset(); });
    extra.addEventListener('focus', () => { if (extra.value === '0')
        extra.value = ''; });
    extra.addEventListener('blur', () => { if (extra.value === '') {
        extra.value = '0';
        render(0);
    } });
    extra.addEventListener('input', () => { desired.value = ''; if (!extra.value) {
        output.textContent = 'Nhập số lượng đạt tăng thêm.';
        return;
    } render(Number(extra.value)); });
    desired.addEventListener('input', () => { if (!desired.value) {
        output.textContent = 'Nhập điểm ghi nhận muốn đạt.';
        return;
    } const r = requiredGrowth(selected, Number(desired.value)); if (r.extra === null) {
        output.textContent = r.message;
        return;
    } extra.value = String(r.extra); render(r.extra); });
    reset();
}
//# sourceMappingURL=score-simulator.js.map