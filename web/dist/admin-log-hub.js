import { logEsc as esc, logDay as day, logAt as at, logState as state, logPager, logDateFilters, logRange, logDialog, publishLogBadge, compactLogFilters, installLogFilterPopover } from './admin-log-ui.js';
import { collectionPeriod } from './admin-collection.js';
function phaseName(v) { if (v === 'national')
    return 'Tổng hợp toàn quốc'; const [type, year, value] = v.split('-'); return collectionPeriod({ type: type ?? '', year: Number(year), month: Number(value), quarter: Number(value) }); }
function phaseTable(phases) { return `<table class="log-table"><thead><tr><th>Kỳ báo cáo</th><th>Khối tỉnh hoàn tất</th><th>Lỗi</th><th>Gói toàn quốc</th></tr></thead><tbody>${phases.length ? phases.map(p => `<tr><th>${esc(phaseName(p.period))}</th><td class="log-number">${p.completed}/${p.expected}</td><td class="log-number">${p.failed}</td><td>${state(p.national)}</td></tr>`).join('') : '<tr><td colspan="4">Chưa có kết quả theo kỳ.</td></tr>'}</tbody></table>`; }
export function renderLogToday(r) {
    return `<p class="log-context">Ngày vận hành <strong>${day(r.day)}</strong> · Dữ liệu <strong>${day(r.daily.reportDate)}</strong></p><div class="log-summary">
 <article><h3>Cào dữ liệu · 05:00</h3>${state(r.daily.state)}<strong>${r.daily.completed}/${r.daily.expected} khối tỉnh–kỳ</strong><small>${r.daily.nationalCompleted}/3 gói toàn quốc · ${r.daily.failed} khối lỗi</small></article>
 <article><h3>Đối chiếu kỳ đã kết thúc · 06:00</h3>${state(r.source.state)}<strong>${r.source.expected == null ? 'Chưa có kết quả' : `${r.source.completed}/${r.source.expected} kỳ tháng`}</strong><small>${esc(r.source.reason ?? 'Bản mẫu riêng, không cập nhật dữ liệu chính.')}</small></article>
 <article><h3>Cảnh báo nguồn</h3><strong>${r.alerts == null ? 'Chưa đọc được' : `${r.alerts.open} chưa xử lý`}</strong><small>${r.alerts == null ? 'Chưa thể kết luận nguồn không thay đổi.' : `${r.alerts.unread} chưa đọc`}</small><button type="button" data-log-go="source">Xem cảnh báo</button></article></div>
 ${r.control === 'open' ? '<p class="log-warning">Nguồn đang tạm dừng an toàn. Nhật ký không tự mở lại nguồn.</p>' : ''}
 ${r.daily.state === 'NEEDS_CHECK' ? '<p class="log-warning">Nhật ký đang chạy nhưng đã lâu chưa cập nhật. Cần kiểm tra tiến trình; chưa kết luận bộ cào vẫn hoạt động.</p>' : ''}
 <div class="log-title-row"><h3>Kết quả theo kỳ báo cáo</h3><button type="button" data-daily-detail="${esc(r.daily.reportDate)}">Xem chi tiết</button></div>${phaseTable(r.daily.phases)}
 <p class="log-updated">Cập nhật nhật ký: ${esc(at(r.daily.updatedAt))} · Kiểm tra: ${esc(at(r.checkedAt))}</p>`;
}
export function renderDailyHistory(r) {
    return `<table class="log-table"><thead><tr><th>Ngày chạy</th><th>Ngày dữ liệu</th><th>Cào 05:00</th><th>Đối chiếu 06:00</th><th>Lỗi / cảnh báo</th><th>Thao tác</th></tr></thead><tbody>${r.items.map(i => `<tr><td>${day(i.runDate)}</td><td>${day(i.reportDate)}</td><td>${state(i.state)}<small>${i.completed}/${i.expected} khối</small></td><td>${state(i.source?.state ?? 'UNAVAILABLE')}</td><td class="log-number">${i.failed} lỗi<small>${i.alerts ?? 0} cảnh báo</small></td><td><button type="button" data-daily-detail="${esc(i.reportDate)}">Chi tiết</button></td></tr>`).join('') || '<tr><td colspan="6">Không có ngày phù hợp bộ lọc.</td></tr>'}</tbody></table>${logPager(r.page, r.total)}`;
}
export function renderDailyDetail(r, filter = '') {
    return `<p>Ngày chạy ${day(r.runDate)} · Dữ liệu ${day(r.reportDate)} · ${state(r.state)} · ${r.completed}/${r.expected} khối</p>${phaseTable(r.phases)}
 <div class="log-title-row"><h3>Nhật ký khối dữ liệu</h3><label>Trạng thái<select data-block-state>${[['', 'Tất cả'], ['issues', 'Chỉ lỗi / tạm dừng'], ['SUCCESS', 'Thành công'], ['RUNNING', 'Đang chạy'], ['RETRYING', 'Đang thử lại']].map(([v, t]) => `<option value="${v}" ${filter === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label></div>
 <table class="log-table"><thead><tr><th>Tỉnh</th><th>Kỳ</th><th>Trạng thái</th><th>Thông tin</th></tr></thead><tbody>${r.items.map(i => `<tr><td>${esc(i.province)}</td><td>${esc(phaseName(i.period))}</td><td>${state(i.state)}</td><td>${esc(i.error ?? i.reason ?? (i.retryAttempt ? `Thử lại lần ${i.retryAttempt}` : '—'))}</td></tr>`).join('') || '<tr><td colspan="4">Chưa có khối phù hợp. Trạng thái chưa chạy/chưa đọc được không đồng nghĩa không có lỗi.</td></tr>'}</tbody></table>${logPager(r.page, r.total, 10, 'data-block-page')}`;
}
function renderJobs(r, user) {
    return `<table class="log-table"><thead><tr><th>${user ? 'Người yêu cầu' : 'Nguồn'}</th><th>Tỉnh / Thủ tục</th><th>Kỳ báo cáo</th><th>Trạng thái</th><th>Thời gian tạo</th><th>Thao tác</th></tr></thead><tbody>${r.jobs.map(j => {
        const full = (j.formalityName ?? j.formalityId ?? 'Tất cả TTHC').replace(' · ', ' - ');
        return `<tr><td>${esc(j.requestedBy.join(', ') || 'Hệ thống / quản trị')}</td><td>${esc(j.province)}<small class="log-ellipsis" title="${esc(full)}">${esc(full)}</small></td><td>${esc(collectionPeriod(j.period))}</td><td>${state(r.control.state === 'open' && ['queued', 'running'].includes(j.state) ? 'paused' : j.state)}</td><td>${esc(at(j.createdAt))}</td><td><button type="button" data-job-detail="${esc(j.id)}">Chi tiết</button></td></tr>`;
    }).join('') || '<tr><td colspan="6">Không có lượt khai thác phù hợp.</td></tr>'}</tbody></table>${logPager(Math.floor(r.offset / 10) + 1, r.total)}`;
}
export function installLogHub(root, api, provinces = []) {
    const today = document.createElement('section');
    today.dataset.logView = 'today';
    today.dataset.collectionMonitor = 'true';
    today.innerHTML = '<div class="log-title-row"><h2>Tổng quan hôm nay</h2><button type="button" data-today-refresh>Làm mới</button></div><p data-today-message role="status"></p><div data-today-body></div>';
    const history = document.createElement('section');
    history.dataset.logView = 'history';
    history.hidden = true;
    history.innerHTML = `<div class="log-title-row"><h2>Lịch sử khai thác</h2><button type="button" data-history-refresh>Làm mới</button></div>${compactLogFilters('<label class="log-field-source">Nguồn<select data-history-source><option value="system">Hệ thống</option><option value="user">Yêu cầu tra cứu</option></select></label><label class="log-field-kind" data-history-type-label>Loại nhật ký<select data-history-type><option value="daily">Cào hằng ngày</option><option value="jobs">Lệnh khai thác quản trị</option><option value="batches">Đợt cập nhật cũ</option><option value="probe">Kiểm chứng dữ liệu cũ</option></select></label><label class="log-field-state">Trạng thái<select data-history-state></select></label>', logDateFilters() + '<label class="log-check" data-issues-label><input type="checkbox" data-history-issues>Chỉ ngày có lỗi hoặc cảnh báo</label>')}<p data-history-message role="status"></p><div data-history-body></div>`;
    root.append(today, history);
    history.querySelector('.log-filter-grid').insertAdjacentHTML('beforeend', `<label class="log-field-wide" data-job-filter>Tỉnh/thành phố<select data-job-province><option value="">Tất cả</option>${provinces.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select></label><label data-job-filter>Loại kỳ<select data-job-period><option value="">Tất cả</option><option value="month">Tháng</option><option value="quarter">Quý</option><option value="year">Năm</option></select></label><label data-job-filter>Năm<input type="number" min="2000" max="2100" data-job-year placeholder="Tất cả"></label><label data-job-filter>Kỳ cụ thể<select data-job-value><option value="">Tất cả</option></select></label>`);
    const todayMessage = today.querySelector('[data-today-message]'), todayBody = today.querySelector('[data-today-body]');
    const historyMessage = history.querySelector('[data-history-message]'), historyBody = history.querySelector('[data-history-body]');
    const source = history.querySelector('[data-history-source]'), kind = history.querySelector('[data-history-type]'), status = history.querySelector('[data-history-state]');
    let currentPage = 1, historyRead = 0, todayRead = 0, poll, loadingToday = false, jobs = [], active = 'today';
    const visible = () => active === 'today' && !today.hidden && !today.closest('[data-admin-panel]')?.hidden && document.visibilityState === 'visible';
    function stop() { clearTimeout(poll); }
    async function loadToday() {
        if (loadingToday || !visible())
            return;
        loadingToday = true;
        const revision = ++todayRead;
        stop();
        todayMessage.textContent = 'Đang tải…';
        try {
            const r = await api('admin/logs/today');
            if (revision !== todayRead)
                return;
            todayBody.innerHTML = renderLogToday(r);
            todayMessage.textContent = '';
            if (r.alerts)
                publishLogBadge(root, r.alerts.open);
            if (r.needsRefresh && visible())
                poll = setTimeout(() => void loadToday(), 10000);
        }
        catch (e) {
            if (revision === todayRead) {
                todayBody.innerHTML = '';
                todayMessage.textContent = e instanceof Error ? e.message : 'Chưa đọc được kết quả hôm nay.';
            }
        }
        finally {
            loadingToday = false;
        }
    }
    function controls() {
        const daily = source.value === 'system' && kind.value === 'daily', archive = source.value === 'system' && ['batches', 'probe'].includes(kind.value);
        history.querySelector('[data-history-type-label]').hidden = source.value !== 'system';
        history.querySelector('[data-issues-label]').hidden = !daily;
        for (const input of history.querySelectorAll('[data-log-from],[data-log-to]'))
            input.disabled = archive;
        status.disabled = archive;
        history.querySelectorAll('[data-job-filter]').forEach(label => label.hidden = daily || archive);
        const entries = daily ? [['COMPLETE', 'Hoàn tất'], ['RUNNING', 'Đang chạy'], ['INCOMPLETE', 'Chưa hoàn tất'], ['HALTED', 'Tạm dừng'], ['NOT_STARTED', 'Chưa chạy'], ['NEEDS_CHECK', 'Cần kiểm tra'], ['UNREADABLE', 'Chưa đọc được']] : [['queued', 'Đang chờ'], ['running', 'Đang chạy'], ['succeeded', 'Thành công'], ['failed', 'Lỗi'], ['halted', 'Tạm dừng']];
        status.innerHTML = '<option value="">Tất cả</option>' + entries.map(([v, t]) => `<option value="${v}">${t}</option>`).join('');
    }
    controls();
    installLogFilterPopover(history, () => { controls(); void loadHistory(); });
    async function loadHistory(page = 1) {
        const revision = ++historyRead;
        historyMessage.textContent = 'Đang tải…';
        historyBody.querySelectorAll('button').forEach(b => b.disabled = true);
        try {
            const params = new URLSearchParams({ page: String(page) });
            let html = '';
            if (source.value === 'system' && ['batches', 'probe'].includes(kind.value)) {
                params.set('kind', kind.value);
                const r = await api('admin/logs/archive?' + params);
                if (revision !== historyRead)
                    return;
                html = kind.value === 'probe' ? (r.probe ? `<h3>${esc(r.probe.label)} ${state(r.probe.state)}</h3><table class="log-table"><thead><tr><th>Kỳ</th><th>Thành công</th><th>Lỗi</th></tr></thead><tbody>${r.probe.phases.map(p => `<tr><td>${esc(phaseName(p.period))}</td><td>${p.counts.SUCCESS ?? 0}/${p.total}</td><td>${(p.counts.FAILED ?? 0) + (p.counts.HALTED ?? 0)}</td></tr>`).join('')}</tbody></table><p>${r.probe.errors.map(e => esc(`${e.province ?? ''} · ${e.error ?? ''}`)).join(' · ')}</p>` : '<p>Chưa có nhật ký kiểm chứng cũ.</p>') :
                    `<table class="log-table"><thead><tr><th>Kỳ</th><th>Trạng thái</th><th>Hoàn tất</th><th>Lỗi</th><th>Cập nhật</th></tr></thead><tbody>${r.items.map(b => `<tr><td>${esc(collectionPeriod(b.period))}</td><td>${state(b.state)}</td><td>${b.completed + b.skipped}/${b.total}</td><td>${b.failed}</td><td>${esc(at(b.updatedAt))}</td></tr>`).join('') || '<tr><td colspan="5">Chưa có đợt cập nhật cũ.</td></tr>'}</tbody></table>${logPager(r.page, r.total)}`;
                currentPage = r.page ?? 1;
            }
            else {
                logRange(history, params);
                if (status.value)
                    params.set('state', status.value);
                if (source.value === 'system' && kind.value === 'daily') {
                    if (history.querySelector('[data-history-issues]').checked)
                        params.set('issuesOnly', 'true');
                    const r = await api('admin/logs/daily?' + params);
                    if (revision !== historyRead)
                        return;
                    currentPage = r.page;
                    html = renderDailyHistory(r);
                }
                else {
                    params.delete('page');
                    params.set('offset', String((page - 1) * 10));
                    params.set('limit', '10');
                    params.set('source', source.value);
                    params.set('compact', 'true');
                    for (const [key, selector] of [['provinceId', '[data-job-province]'], ['periodType', '[data-job-period]'], ['year', '[data-job-year]'], ['periodValue', '[data-job-value]']]) {
                        const v = history.querySelector(selector).value;
                        if (v)
                            params.set(key, v);
                    }
                    const r = await api('admin/collection-log?' + params);
                    if (revision !== historyRead)
                        return;
                    currentPage = Math.floor(r.offset / 10) + 1;
                    jobs = r.jobs;
                    html = renderJobs(r, source.value === 'user');
                }
            }
            historyBody.innerHTML = html;
            historyMessage.textContent = '';
        }
        catch (e) {
            if (revision !== historyRead)
                return;
            historyBody.innerHTML = '';
            historyMessage.textContent = e instanceof Error ? e.message : 'Chưa đọc được lịch sử.';
        }
    }
    async function openDaily(reportDate) {
        if (root.querySelector('.admin-log-dialog'))
            return;
        const { dialog, body } = logDialog(root, 'Chi tiết cào dữ liệu · ' + day(reportDate));
        let revision = 0, filter = '';
        async function load(page = 1) { const seq = ++revision; body.setAttribute('aria-busy', 'true'); try {
            const q = new URLSearchParams({ page: String(page) });
            if (filter)
                q.set('state', filter);
            const r = await api(`admin/logs/daily/${reportDate}?${q}`);
            if (dialog.isConnected && seq === revision)
                body.innerHTML = renderDailyDetail(r, filter);
        }
        catch (e) {
            if (dialog.isConnected && seq === revision)
                body.textContent = e instanceof Error ? e.message : 'Chưa đọc được chi tiết.';
        }
        finally {
            if (seq === revision)
                body.removeAttribute('aria-busy');
        } }
        body.addEventListener('change', e => { const input = e.target.closest('[data-block-state]'); if (input) {
            filter = input.value;
            void load();
        } });
        body.addEventListener('click', e => { const button = e.target.closest('[data-block-page]'); if (button && !button.disabled)
            void load(Number(button.dataset.blockPage)); });
        await load();
    }
    root.addEventListener('click', e => {
        const target = e.target, button = target.closest('button');
        if (!button || button.disabled)
            return;
        if (button.dataset.dailyDetail)
            void openDaily(button.dataset.dailyDetail);
        if (button.dataset.logGo)
            root.querySelector(`[data-log-tab="${button.dataset.logGo}"]`)?.click();
        if (button.dataset.jobDetail) {
            const job = jobs.find(j => j.id === button.dataset.jobDetail);
            if (!job)
                return;
            const { body } = logDialog(root, 'Chi tiết lượt khai thác');
            body.innerHTML = `<dl class="log-fields">${[['Tỉnh', job.province], ['Người yêu cầu', job.requestedBy.join(', ') || 'Hệ thống / quản trị'], ['Thủ tục', job.formalityName ?? job.formalityId ?? 'Tất cả TTHC'], ['Kỳ', collectionPeriod(job.period)], ['Trạng thái', job.state], ['Lượt xử lý', job.attempts], ['Nhóm cần lấy', job.expectedGroups], ['Tạo lúc', at(job.createdAt)], ['Cập nhật', at(job.updatedAt)], ['Lần thử tiếp', at(job.nextRunAt)], ['Lỗi', job.errorKind ?? '—']].map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`;
        }
    });
    today.querySelector('[data-today-refresh]').addEventListener('click', () => void loadToday());
    history.querySelector('[data-history-refresh]').addEventListener('click', () => void loadHistory(currentPage));
    history.addEventListener('change', e => { const target = e.target; if (target.matches('[data-history-source],[data-history-type]'))
        controls(); if (target.matches('[data-job-period]')) {
        const type = history.querySelector('[data-job-period]').value, input = history.querySelector('[data-job-value]');
        input.innerHTML = '<option value="">Tất cả</option>' + Array.from({ length: type === 'month' ? 12 : type === 'quarter' ? 4 : 0 }, (_, i) => `<option value="${i + 1}">${type === 'month' ? 'Tháng' : 'Quý'} ${i + 1}</option>`).join('');
        input.disabled = !['month', 'quarter'].includes(type);
    } void loadHistory(); });
    historyBody.addEventListener('click', e => { const b = e.target.closest('[data-log-page]'); if (b && !b.disabled)
        void loadHistory(Number(b.dataset.logPage)); });
    root.addEventListener('qd766-log-view', e => { active = e.detail; stop(); if (active === 'today')
        void loadToday(); if (active === 'history')
        void loadHistory(currentPage); });
    root.addEventListener('click', e => { const b = e.target.closest('[data-admin-section]'); if (b && b.dataset.adminSection !== 'collection') {
        active = '';
        stop();
    } });
    document.addEventListener('visibilitychange', () => { stop(); if (visible())
        void loadToday(); });
}
//# sourceMappingURL=admin-log-hub.js.map