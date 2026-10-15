export const logEsc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const logNum = (v) => v.toLocaleString('vi-VN');
export const logDay = (v) => /^\d{4}-\d{2}-\d{2}$/.test(v) ? v.split('-').reverse().join('/') : '—';
export const logAt = (v) => v ? new Date(v).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : '—';
export const logLabels = { COMPLETE: 'Hoàn tất', SUCCESS: 'Thành công', RUNNING: 'Đang chạy', RETRYING: 'Đang thử lại', FAILED: 'Lỗi', INCOMPLETE: 'Chưa hoàn tất', HALTED: 'Tạm dừng', NOT_STARTED: 'Chưa chạy', NOT_DUE: 'Chưa đến lịch', UNREADABLE: 'Chưa đọc được', UNAVAILABLE: 'Chưa đọc được', NEEDS_CHECK: 'Cần kiểm tra', queued: 'Đang chờ', running: 'Đang chạy', succeeded: 'Thành công', failed: 'Lỗi', halted: 'Tạm dừng', complete: 'Hoàn tất', incomplete: 'Chưa hoàn tất', waiting: 'Chờ cào 05:00', paused: 'Tạm dừng an toàn', 'not-checked': 'Chưa kiểm tra', 'not-started': 'Chưa chạy', 'not-due': 'Chưa đến lịch' };
export const logState = (v) => `<span class="collection-state state-${logEsc(v.toLowerCase())}">${logEsc(logLabels[v] ?? v)}</span>`;
export function logPager(page, total, size = 10, attribute = 'data-log-page') {
    const pages = Math.max(1, Math.ceil(total / size));
    return `<nav class="log-pager" aria-label="Phân trang"><span>${logNum(total)} bản ghi · Trang ${page}/${pages}</span><div><button type="button" ${attribute}="${page - 1}" ${page <= 1 ? 'disabled' : ''}>Trước</button><button type="button" ${attribute}="${page + 1}" ${page >= pages ? 'disabled' : ''}>Sau</button></div></nav>`;
}
export function logDateFilters() { return '<label>Từ ngày<input type="date" lang="vi" data-log-from aria-label="Từ ngày"></label><label>Đến ngày<input type="date" lang="vi" data-log-to aria-label="Đến ngày"></label>'; }
export function compactLogFilters(primary, advanced = logDateFilters()) {
    return `<div class="log-filters log-toolbar"><div class="log-filter-primary">${primary}</div><div class="log-filter-actions"><details class="log-filter-more" data-log-filter-more><summary><svg width="14" height="14" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M3 5h14M5.5 10h9M8 15h4" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>Bộ lọc<span data-log-filter-count hidden></span></summary><div class="log-filter-popover"><div class="log-filter-caption">Lọc chi tiết</div><div class="log-filter-grid">${advanced}</div></div></details><button type="button" class="log-reset" data-log-reset>Đặt lại</button></div></div>`;
}
export function installLogFilterPopover(section, onReset) {
    const details = section.querySelector('[data-log-filter-more]'), badge = section.querySelector('[data-log-filter-count]');
    function update() {
        const count = [...details.querySelectorAll('input,select')].filter(input => !input.disabled && !input.closest('[hidden]') && (input instanceof HTMLInputElement && input.type === 'checkbox' ? input.checked : !!input.value)).length;
        badge.textContent = String(count);
        badge.hidden = count === 0;
        section.querySelectorAll('select').forEach(select => select.title = select.selectedOptions[0]?.textContent ?? '');
    }
    section.addEventListener('change', update);
    section.querySelector('[data-log-reset]').addEventListener('click', () => {
        section.querySelectorAll('.log-filters input,.log-filters select').forEach(input => {
            if (input instanceof HTMLSelectElement)
                input.selectedIndex = 0;
            else if (input.type === 'checkbox')
                input.checked = false;
            else
                input.value = '';
        });
        details.open = false;
        onReset();
        update();
    });
    details.addEventListener('keydown', event => { if (event.key === 'Escape') {
        event.stopPropagation();
        details.open = false;
        details.querySelector('summary')?.focus();
    } });
    document.addEventListener('pointerdown', event => { if (details.open && !details.contains(event.target))
        details.open = false; });
    update();
    return update;
}
export function logRange(section, params) {
    const from = section.querySelector('[data-log-from]')?.value, to = section.querySelector('[data-log-to]')?.value;
    if (from && to && from > to)
        throw new Error('Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.');
    if (from)
        params.set('fromDate', from);
    if (to)
        params.set('toDate', to);
}
export function logDialog(root, title) {
    const previous = document.activeElement, dialog = document.createElement('dialog');
    dialog.className = 'admin-log-dialog';
    const id = 'log-dialog-' + crypto.randomUUID();
    dialog.setAttribute('aria-labelledby', id);
    dialog.innerHTML = `<header><h2 id="${id}">${logEsc(title)}</h2><button type="button" data-log-close>Đóng</button></header><div data-log-dialog-body role="status">Đang tải…</div>`;
    root.append(dialog);
    dialog.querySelector('[data-log-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { dialog.remove(); if (previous?.isConnected)
        previous.focus({ preventScroll: true }); });
    dialog.showModal();
    return { dialog, body: dialog.querySelector('[data-log-dialog-body]') };
}
export function publishLogBadge(root, count) { root.dispatchEvent(new CustomEvent('qd766-source-count', { detail: count })); }
//# sourceMappingURL=admin-log-ui.js.map