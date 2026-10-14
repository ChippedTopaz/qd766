export const dailyComboOptions = { height: 290, left: 48, right: 48, top: 32, bottom: 42, tickSpacing: 62,
    barColor: '#3b82f6', barOpacity: .4, lineColor: '#ea8809', markerRadius: 3, ratioMaximum: 100, y1Minimum: 0, tickIntervals: 4 };
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = (v, digits = 0) => v === null ? '—' : v.toLocaleString('vi-VN', { maximumFractionDigits: digits });
const label = (day) => day.split('-').reverse().join('/');
const coord = (v) => String(Math.round(v * 100) / 100);
const axisNumber = (v) => num(Math.round(v), 0);
export function comboTooltip(model, index) {
    const p = model.points[index];
    if (!p)
        return '';
    const delta = p.delta === null ? '—' : `${p.delta > 0 ? '+' : ''}${num(p.delta)}`;
    const value = model.mode === 'ratio' ? p.ratio : p.score;
    return `Ngày: ${label(p.day)}\nPhát sinh: ${delta}\n${model.mode === 'ratio' ? 'Tỷ lệ' : 'Điểm số'}: ${num(value, 2)}${value === null ? '' : model.mode === 'ratio' ? '%' : ' điểm'}`;
}
/** Greedy time ticks maintain a minimum pixel separation, including end labels. */
export function comboTickIndices(count, plotWidth) {
    if (count <= 1)
        return count ? [0] : [];
    const step = plotWidth / count, indices = [0];
    let last = 0;
    for (let i = 1; i < count; i++)
        if ((i - last) * step >= dailyComboOptions.tickSpacing) {
            indices.push(i);
            last = i;
        }
    if ((count - 1 - last) * step >= dailyComboOptions.tickSpacing)
        indices.push(count - 1);
    else if (indices.length > 1 && (count - 1 - indices[indices.length - 2]) * step >= dailyComboOptions.tickSpacing)
        indices[indices.length - 1] = count - 1;
    return indices;
}
/** Monotone cubic interpolation: smooth, without inventing overshoots between observations. */
export function smoothSegments(points) {
    const segments = [];
    let run = [];
    for (const p of [...points, null]) {
        if (p)
            run.push(p);
        else if (run.length) {
            segments.push(run);
            run = [];
        }
    }
    return segments.filter(s => s.length > 1).map(s => {
        const slopes = s.slice(1).map((p, i) => (p.y - s[i].y) / (p.x - s[i].x));
        const tangent = s.map((_, i) => i === 0 ? slopes[0] : i === s.length - 1 ? slopes[i - 1] : slopes[i - 1] * slopes[i] <= 0 ? 0 : 2 * slopes[i - 1] * slopes[i] / (slopes[i - 1] + slopes[i]));
        let path = `M ${coord(s[0].x)} ${coord(s[0].y)}`;
        for (let i = 1; i < s.length; i++) {
            const a = s[i - 1], b = s[i], dx = (b.x - a.x) / 3;
            path += ` C ${coord(a.x + dx)} ${coord(a.y + tangent[i - 1] * dx)} ${coord(b.x - dx)} ${coord(b.y - tangent[i] * dx)} ${coord(b.x)} ${coord(b.y)}`;
        }
        return path;
    });
}
function bounds(model, width) {
    const o = dailyComboOptions, w = Math.max(240, width), plot = w - o.left - o.right, h = o.height - o.top - o.bottom;
    const values = model.points.flatMap(p => p.delta === null || p.delta < 0 ? [] : [p.delta]);
    const max = Math.max(0, ...values), low = o.y1Minimum;
    // Integer steps and four intervals yield five shared gridlines, with zero
    // always at the plot bottom. Small counts get 0/1/2/3/4 instead of decimals.
    const high = Math.max(1, Math.ceil(max / o.tickIntervals)) * o.tickIntervals;
    const maximum = model.mode === 'ratio' ? o.ratioMaximum : Math.max(1, ...model.points.flatMap(p => [p.maximum ?? 0, p.score ?? 0]));
    return { width: w, plot, height: h, low, high, maximum,
        x: (i) => o.left + (i + .5) * plot / Math.max(1, model.points.length),
        y: (n) => o.top + (high - n) / (high - low) * h,
        y2: (n) => o.top + (1 - n / maximum) * h };
}
export function renderComboGraphic(model, width = 360) {
    const b = bounds(model, width), o = dailyComboOptions, zero = b.y(0), n = model.points.length;
    const line = model.points.map((p, i) => { const v = model.mode === 'ratio' ? p.ratio : p.score; return v === null ? null : { x: b.x(i), y: b.y2(v) }; });
    const ticks = comboTickIndices(n, b.plot), barWidth = Math.max(.5, Math.min(16, b.plot / Math.max(n, 1) * .58));
    return `<svg class="daily-combo-svg" viewBox="0 0 ${b.width} ${o.height}" aria-hidden="true" focusable="false">
 <text x="${o.left}" y="14" class="daily-combo-axis-title">Phát sinh</text><text x="${b.width - o.right}" y="14" text-anchor="end" class="daily-combo-axis-title">${model.mode === 'ratio' ? 'Tỷ lệ (%)' : 'Điểm số'}</text>
 ${Array.from({ length: o.tickIntervals + 1 }, (_, i) => { const f = i / o.tickIntervals, y = o.top + f * b.height; return `<line x1="${o.left}" x2="${b.width - o.right}" y1="${y}" y2="${y}" class="daily-combo-grid"/><text data-combo-y1="${b.high - f * (b.high - b.low)}" x="${o.left - 8}" y="${y + 4}" text-anchor="end">${esc(axisNumber(b.high - f * (b.high - b.low)))}</text><text data-combo-y2="${(1 - f) * b.maximum}" x="${b.width - o.right + 8}" y="${y + 4}">${esc(num((1 - f) * b.maximum, model.mode === 'ratio' ? 0 : 2))}</text>`; }).join('')}
 <line x1="${o.left}" x2="${b.width - o.right}" y1="${coord(zero)}" y2="${coord(zero)}" class="daily-combo-zero"/>
 ${model.points.map((p, i) => `<g data-daily-combo-date="${esc(p.day)}"${p.delta === null ? '' : ` data-daily-combo-delta="${p.delta}"`}>
 ${p.delta === null ? '' : p.delta < 0 ? `<path data-combo-correction d="M ${coord(b.x(i) - 3)} ${coord(zero - 6)} L ${coord(b.x(i) + 3)} ${coord(zero - 6)} L ${coord(b.x(i))} ${coord(zero - 1)} Z" fill="${o.barColor}" fill-opacity="${o.barOpacity}"/>` : `<rect x="${coord(b.x(i) - barWidth / 2)}" y="${coord(b.y(p.delta))}" width="${coord(barWidth)}" height="${coord(zero - b.y(p.delta))}" fill="${o.barColor}" fill-opacity="${o.barOpacity}" rx="1"/>`}</g>`).join('')}
 ${smoothSegments(line).map(d => `<path d="${d}" fill="none" stroke="${o.lineColor}" stroke-width="2.3"/>`).join('')}
 ${line.map(p => p ? `<circle cx="${coord(p.x)}" cy="${coord(p.y)}" r="${n > 90 ? 1.7 : o.markerRadius}" fill="white" stroke="${o.lineColor}" stroke-width="1.8"/>` : '').join('')}
 ${ticks.map(i => `<text x="${coord(b.x(i))}" y="${o.height - 18}" text-anchor="middle" data-combo-tick="${i}">${esc(label(model.points[i].day).slice(0, 5))}</text>`).join('')}
 <line data-combo-hover hidden x1="0" x2="0" y1="${o.top}" y2="${o.top + b.height}" class="daily-combo-hover"/>
 </svg>`;
}
export function renderComboChart(model) {
    return `<div class="daily-combo-legend"><span><i class="daily-combo-bar-key"></i>Phát sinh</span><span><i class="daily-combo-line-key"></i>${model.mode === 'ratio' ? 'Tỷ lệ' : 'Điểm số'}</span></div>
 <div class="daily-combo" data-daily-combo="${esc(JSON.stringify(model))}" tabindex="0" role="img" aria-label="${esc(model.name)}: cột phát sinh theo ngày và đường ${model.mode === 'ratio' ? 'tỷ lệ' : 'điểm số'}. Dùng phím trái, phải để xem từng ngày.">
 <div data-combo-graphic>${renderComboGraphic(model)}</div><div class="daily-combo-tooltip" data-combo-tooltip role="status" hidden></div></div>`;
}
export function bindComboCharts(doc) {
    const observers = [];
    doc.querySelectorAll('[data-daily-combo]').forEach(host => {
        const model = JSON.parse(host.dataset.dailyCombo), graphic = host.querySelector('[data-combo-graphic]'), tip = host.querySelector('[data-combo-tooltip]');
        let width = Math.max(240, host.clientWidth || 360), selected = -1;
        const hide = () => { tip.hidden = true; graphic.querySelector('[data-combo-hover]')?.setAttribute('hidden', ''); };
        const show = (index) => {
            if (!model.points.length)
                return;
            selected = Math.max(0, Math.min(index, model.points.length - 1));
            tip.textContent = comboTooltip(model, selected);
            tip.hidden = false;
            const b = bounds(model, width), x = b.x(selected);
            tip.style.left = `${Math.max(0, Math.min(x - tip.offsetWidth / 2, width - tip.offsetWidth))}px`;
            const line = graphic.querySelector('[data-combo-hover]');
            line?.removeAttribute('hidden');
            line?.setAttribute('x1', coord(x));
            line?.setAttribute('x2', coord(x));
        };
        const resize = () => {
            const next = Math.max(240, host.clientWidth || 360);
            if (next === width && graphic.dataset.measured)
                return;
            width = next;
            graphic.innerHTML = renderComboGraphic(model, width);
            graphic.dataset.measured = 'true';
            if (selected >= 0 && !tip.hidden)
                show(selected);
        };
        resize();
        if (typeof ResizeObserver !== 'undefined') {
            const observer = new ResizeObserver(resize);
            observer.observe(host);
            observers.push(observer);
        }
        const pointer = (event) => {
            const rect = graphic.getBoundingClientRect(), b = bounds(model, width), x = (event.clientX - rect.left) * width / Math.max(1, rect.width);
            if (x < dailyComboOptions.left || x > width - dailyComboOptions.right) {
                hide();
                return;
            }
            show(Math.floor((x - dailyComboOptions.left) / b.plot * model.points.length));
        };
        host.addEventListener('pointermove', pointer);
        host.addEventListener('pointerdown', pointer);
        host.addEventListener('pointerleave', hide);
        host.addEventListener('blur', hide);
        host.addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Escape'].includes(event.key))
                return;
            event.preventDefault();
            if (event.key === 'Escape') {
                hide();
                return;
            }
            show(event.key === 'Home' ? 0 : event.key === 'End' ? model.points.length - 1 : selected < 0 ? 0 : selected + (event.key === 'ArrowLeft' ? -1 : 1));
        });
    });
    return () => observers.forEach(o => o.disconnect());
}
//# sourceMappingURL=daily-combo-chart.js.map