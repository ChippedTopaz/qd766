const memory = new Map();
let pollTimer;
let pollVersion = 0;
export function stopPaidAnalysisPolling() { clearTimeout(pollTimer); pollTimer = undefined; pollVersion++; }
export function clearPaidAnalysis() { stopPaidAnalysisPolling(); memory.clear(); }
const pending = (analysis) => analysis?.state === 'queued' || analysis?.state === 'running';
const esc = (value) => value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const key = (s) => JSON.stringify([s.rootDepartmentId, s.unitId, s.periodType, s.year, s.periodValue]);
const entry = (s) => { const k = key(s); if (!memory.has(k))
    memory.set(k, { busy: false, confirming: false, error: '', token: null, analysis: null }); return memory.get(k); };
export function renderPaidAnalysis(selection, authenticated, enabled = true) {
    const local = entry(selection);
    const analysis = local.analysis;
    const renderCards = (kind) => {
        const cards = analysis?.result?.cards.filter(c => c.kind === kind) ?? [];
        return cards.length ? cards.map(c => `<article class="analysis-card"><h3>${esc(c.title)}</h3><p>${esc(c.evidence)}</p><p>${esc(c.recommendation ?? c.action)}</p><button class="text-button" data-analysis-group="${esc(c.groupId)}">Xem chỉ tiêu →</button></article>`).join('') : '<p>Chưa có nhận định trong nhóm này.</p>';
    };
    const stale = analysis?.state === 'ready' && Date.parse(selection.capturedAt) > Date.parse(analysis.capturedAt);
    const queueStatus = pending(analysis) ? `<div class="credit-summary" role="status"><span>${analysis?.state === 'queued' ? `Đang chờ · Vị trí ${esc(String(analysis.queuePosition ?? '—'))}` : 'Đang phân tích'}</span><strong>20 Credit đang giữ</strong>${analysis?.state === 'queued' ? '<button class="btn small" data-analysis-cancel-job>Hủy lượt chờ</button>' : ''}</div><p>Thời gian chờ tối đa ${esc(String(analysis?.queueWaitMinutes ?? 10))} phút. Credit chưa ghi nhận thu.</p>` : '';
    const confirmation = local.confirming ? `<div class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="analysis-confirm-title"><div class="modal collection-confirm"><div class="modal-top"><strong id="analysis-confirm-title">Phân tích, đánh giá</strong><button class="btn small" data-analysis-cancel>Đóng</button></div><div class="brief"><h2>Phân tích số liệu bằng Gemini</h2><p>Đưa ra vấn đề cần ưu tiên và kết quả tốt cần duy trì cho cơ quan, kỳ đang chọn.</p><div class="credit-summary"><span>Credit sử dụng</span><strong>20 Credit</strong></div><p>Credit được ghi nhận khi kết quả được lưu thành công. Hoàn toàn bộ nếu phân tích thất bại.</p><div class="analysis-actions"><button class="btn" data-analysis-cancel>Hủy</button><button class="btn primary" data-analysis-confirm>Phân tích</button></div></div></div></div>` : '';
    return `${confirmation}<section class="panel paid-analysis"><div class="panel-head"><div><h2>Phân tích - đánh giá <span class="analysis-experimental">(Đang thử nghiệm)</span></h2></div><div class="analysis-actions"><button class="btn" data-analysis-read ${local.busy || !authenticated ? 'disabled' : ''}>Xem kết quả đã lưu</button><button class="btn primary" data-analysis-start ${local.busy || pending(analysis) || !enabled || !authenticated || selection.scope !== 'all' ? 'disabled' : ''}>${local.busy ? 'Đang gửi…' : pending(analysis) ? 'Đang chờ / xử lý' : local.token ? 'Tiếp tục lượt phân tích' : analysis?.state === 'ready' ? 'Phân tích lại' : 'Phân tích'}</button></div></div><div class="panel-body" aria-live="polite">${!enabled ? '<p>Phân tích Gemini chưa được kích hoạt.</p>' : ''}${selection.scope !== 'all' ? '<p>Phân tích hiện áp dụng cho tất cả TTHC của cơ quan trong kỳ đang chọn.</p>' : ''}${local.busy ? '<p role="status">Đang xử lý yêu cầu. Anh/chị có thể tiếp tục sử dụng các mục khác.</p>' : ''}${local.error ? `<p class="negative">${esc(local.error)}</p>` : ''}${queueStatus}${analysis ? `<p>Phân tích lúc ${esc(new Date(analysis.createdAt).toLocaleString('vi-VN'))} · Dữ liệu ${esc(new Date(analysis.capturedAt).toLocaleString('vi-VN'))}</p>` : ''}${stale ? '<p>Kết quả đã lưu sử dụng dữ liệu trước lần cập nhật hiện tại.</p>' : ''}</div></section><section class="split bento-insights"><article class="panel"><div class="panel-head"><h2>Vấn đề cần ưu tiên</h2></div><div class="panel-body">${renderCards('priority')}</div></article><article class="panel"><div class="panel-head"><h2>Kết quả tốt cần duy trì</h2></div><div class="panel-body">${renderCards('strength')}</div></article></section>${analysis?.result ? `<details class="comparison-notes"><summary>Lưu ý</summary>${analysis.result.limitations.map(text => `<p>${esc(text)}</p>`).join('')}</details>` : ''}`;
}
export function bindPaidAnalysis(selection, csrf, onChange, onGroup, onWallet) {
    const local = entry(selection);
    const update = (value) => { local.analysis = value; local.token = pending(value) ? value.requestToken ?? local.token : null; local.error = pending(value) || value.state === 'ready' ? '' : value.message; if (value.availableCredits !== undefined)
        onWallet(value.availableCredits, value.reservedCredits ?? 0); };
    const run = async () => {
        if (local.busy || selection.scope !== 'all')
            return;
        local.confirming = false;
        local.busy = true;
        local.error = '';
        local.token ??= crypto.randomUUID();
        onChange();
        try {
            const { scope, capturedAt, ...context } = selection;
            const response = await fetch('/api/v1/me/analysis', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-QD766-CSRF': csrf }, body: JSON.stringify({ ...context, token: local.token, expectedCredits: 20 }) });
            const value = await response.json();
            if (!response.ok) {
                if (response.status < 500)
                    local.token = null;
                throw new Error(typeof value.detail === 'string' ? value.detail : 'Không thực hiện được phân tích.');
            }
            update(value);
        }
        catch (error) {
            local.error = error instanceof Error ? error.message : 'Chưa xác nhận được kết quả. Xem kết quả đã lưu trước khi gửi lại.';
        }
        finally {
            local.busy = false;
            onChange();
        }
    };
    document.querySelector('[data-analysis-start]')?.addEventListener('click', () => {
        if (local.busy || local.confirming || pending(local.analysis) || selection.scope !== 'all')
            return;
        if (local.token) {
            void run();
            return;
        }
        local.confirming = true;
        onChange();
        document.querySelector('[data-analysis-cancel]')?.focus();
    });
    document.querySelector('[data-analysis-confirm]')?.addEventListener('click', () => { if (local.confirming)
        void run(); });
    const cancel = () => { local.confirming = false; onChange(); document.querySelector('[data-analysis-start]')?.focus(); };
    document.querySelectorAll('[data-analysis-cancel]').forEach(button => button.addEventListener('click', cancel));
    document.querySelector('[aria-labelledby="analysis-confirm-title"]')?.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            event.preventDefault();
            cancel();
            return;
        }
        if (event.key === 'Tab') {
            const buttons = Array.from(document.querySelectorAll('[aria-labelledby="analysis-confirm-title"] button'));
            const first = buttons[0], last = buttons[buttons.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last?.focus();
            }
            else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first?.focus();
            }
        }
    });
    document.querySelector('[data-analysis-read]')?.addEventListener('click', async () => {
        if (local.busy)
            return;
        local.busy = true;
        local.error = '';
        onChange();
        try {
            const query = new URLSearchParams({ root_department_id: selection.rootDepartmentId, unit_id: selection.unitId, period_type: selection.periodType, year: String(selection.year) });
            if (selection.periodValue !== null)
                query.set('period_value', String(selection.periodValue));
            const response = await fetch('/api/v1/me/analysis/latest?' + query, { cache: 'no-store' });
            const body = await response.json();
            if (!response.ok)
                throw new Error(body.detail ?? 'Không tải được kết quả.');
            if (body.analysis)
                update(body.analysis);
            else
                local.error = 'Chưa có kết quả phân tích đã lưu cho lựa chọn này.';
        }
        catch (error) {
            local.error = error instanceof Error ? error.message : 'Không tải được kết quả.';
        }
        finally {
            local.busy = false;
            onChange();
        }
    });
    document.querySelectorAll('[data-analysis-group]').forEach(button => button.addEventListener('click', () => onGroup(button.dataset.analysisGroup)));
    document.querySelector('[data-analysis-cancel-job]')?.addEventListener('click', async () => {
        if (local.busy || local.analysis?.state !== 'queued' || !local.token)
            return;
        local.busy = true;
        local.error = '';
        onChange();
        try {
            const { scope, capturedAt, ...context } = selection;
            const response = await fetch('/api/v1/me/analysis/cancel', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-QD766-CSRF': csrf }, body: JSON.stringify({ ...context, token: local.token, expectedCredits: 20 }) });
            const value = await response.json();
            if (!response.ok)
                throw new Error(value.detail ?? 'Không hủy được lượt chờ.');
            update(value);
        }
        catch (error) {
            local.error = error instanceof Error ? error.message : 'Không hủy được lượt chờ.';
        }
        finally {
            local.busy = false;
            onChange();
        }
    });
    stopPaidAnalysisPolling();
    if (pending(local.analysis) && !local.busy) {
        const version = pollVersion;
        const id = local.analysis.id;
        const poll = async () => {
            if (version !== pollVersion)
                return;
            if (document.visibilityState === 'hidden') {
                pollTimer = setTimeout(poll, 5000);
                return;
            }
            try {
                const response = await fetch('/api/v1/me/analysis/' + encodeURIComponent(id) + '/status', { cache: 'no-store' });
                const value = await response.json();
                if (version !== pollVersion)
                    return;
                if (!response.ok)
                    throw new Error(value.detail ?? 'Chưa đọc được trạng thái phân tích.');
                update(value);
            }
            catch (error) {
                if (version !== pollVersion)
                    return;
                local.error = error instanceof Error ? error.message : 'Chưa đọc được trạng thái.';
            }
            onChange();
        };
        pollTimer = setTimeout(poll, 5000);
    }
}
//# sourceMappingURL=paid-analysis.js.map