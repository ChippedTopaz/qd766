import { logEsc as esc, logAt as at, logRange, logPager, logDialog, compactLogFilters, installLogFilterPopover } from './admin-log-ui.js';
export const auditLabels = { 'account.updated': 'Phân quyền / khóa tài khoản', 'trial-credit.updated': 'Cấp Credit', 'subscription.trial-activated': 'Kích hoạt dùng thử', 'subscription.invited-trial-started': 'Bắt đầu dùng thử theo lời mời', 'subscription.backfill-approved': 'Bổ sung dùng thử đã duyệt', 'invitation.created': 'Tạo lời mời', 'invitation.revoked': 'Thu hồi lời mời', 'invitation.redeemed': 'Sử dụng lời mời', 'registration.approved': 'Duyệt đăng ký', 'registration.rejected': 'Từ chối đăng ký', 'registration.assignment-updated': 'Điều chỉnh phạm vi đăng ký', 'registration-link.created': 'Tạo link đăng ký', 'registration-link.revoked': 'Thu hồi link đăng ký', 'formula_configuration_saved': 'Lưu cấu hình công thức', 'analysis_configuration_saved': 'Lưu cấu hình phân tích AI', 'analysis_feature_changed': 'Thay đổi tính năng phân tích AI', 'source-monitor.read': 'Đọc cảnh báo nguồn', 'source-monitor.resolve': 'Xử lý cảnh báo nguồn', 'trivia_question_saved': 'Lưu câu hỏi', 'trivia_question_published': 'Duyệt câu hỏi công khai', 'trivia_questions_imported': 'Nhập câu hỏi', 'trivia_question_deleted': 'Xóa câu hỏi' };
const fields = { before: 'Trước thay đổi', after: 'Sau thay đổi', active: 'Hoạt động', accountId: 'Mã tài khoản', provinceId: 'Tỉnh/thành phố', unitId: 'Cơ quan', accessTier: 'Phạm vi quyền', amount: 'Credit', reason: 'Lý do', creditSource: 'Nguồn Credit', canCollect: 'Quyền khai thác', version: 'Phiên bản', revision: 'Lần cập nhật', group: 'Nhóm', groupId: 'Mã nhóm', state: 'Trạng thái', email: 'Email', startsAt: 'Bắt đầu', endsAt: 'Kết thúc', days: 'Số ngày', enabled: 'Kích hoạt', count: 'Số lượng', duplicates: 'Trùng', registrationId: 'Mã đăng ký', invitationId: 'Mã lời mời', questionId: 'Mã câu hỏi', alertId: 'Mã cảnh báo', linkId: 'Mã link', maxRegistrations: 'Giới hạn đăng ký', deletedAnswers: 'Lượt trả lời đã xóa', affectedAccounts: 'Tài khoản liên quan', clearedPending: 'Lượt chờ đã xóa' };
function value(v, detail) {
    if (v == null)
        return '—';
    if (typeof v === 'boolean')
        return v ? 'Có' : 'Không';
    if (typeof v === 'object')
        return `<dl class="log-fields">${Object.entries(v).map(([k, val]) => `<dt>${esc(fields[k] ?? k)}</dt><dd>${value(val, detail)}</dd>`).join('')}</dl>`;
    return esc(detail.departmentNames[String(v)] ?? ({ agency: 'Cơ quan', province: 'Cả tỉnh', national: 'Toàn quốc', subscription: 'Theo chu kỳ', purchased: 'Bổ sung' }[String(v)]) ?? String(v));
}
export function renderAuditReport(r) { return `<table class="log-table"><thead><tr><th>Thời gian</th><th>Người thực hiện</th><th>Thao tác</th><th>Đối tượng</th><th>Chi tiết</th></tr></thead><tbody>${r.items.map(i => `<tr><td>${esc(at(i.at))}</td><td>${esc(i.actor)}${i.actorEmail ? `<small>${esc(i.actorEmail)}</small>` : ''}</td><td>${esc(auditLabels[i.action] ?? i.action)}</td><td>${esc(i.target)}${i.targetEmail ? `<small>${esc(i.targetEmail)}</small>` : ''}</td><td><button type="button" data-audit-detail="${esc(i.id)}">Chi tiết</button></td></tr>`).join('') || '<tr><td colspan="5">Không có thao tác phù hợp bộ lọc.</td></tr>'}</tbody></table>${logPager(r.page, r.total, 10, 'data-audit-page')}`; }
export function renderAuditDetail(r) { return `<p>${esc(auditLabels[r.action] ?? r.action)} · ${esc(at(r.at))}</p><dl class="log-fields"><dt>Người thực hiện</dt><dd>${esc(r.actor)}${r.actorEmail ? ` · ${esc(r.actorEmail)}` : ''}</dd><dt>Đối tượng</dt><dd>${esc(r.target)}${r.targetEmail ? ` · ${esc(r.targetEmail)}` : ''}</dd></dl>${Object.keys(r.details).length ? value(r.details, r) : '<p>Không có nội dung chi tiết được phép hiển thị.</p>'}`; }
export function installAdminAudit(root, api) {
    const section = root.querySelector('#audit').closest('section');
    section.dataset.logView = 'audit';
    section.hidden = true;
    section.innerHTML = `<div class="log-title-row"><h2>Nhật ký quản trị</h2><button type="button" data-audit-refresh>Làm mới</button></div>${compactLogFilters('<label class="log-search">Tìm đối tượng<input type="search" maxlength="200" data-audit-search placeholder="Tên hoặc email"></label><label class="log-field-actor">Người thực hiện<select data-audit-actor><option value="">Tất cả</option></select></label><label class="log-field-action">Thao tác<select data-audit-action><option value="">Tất cả</option></select></label>')}<p data-audit-message role="status"></p><div data-audit-body></div>`;
    const body = section.querySelector('[data-audit-body]'), message = section.querySelector('[data-audit-message]'), actor = section.querySelector('[data-audit-actor]'), action = section.querySelector('[data-audit-action]'), search = section.querySelector('[data-audit-search]');
    let page = 1, read = 0, timer, opening = false;
    installLogFilterPopover(section, () => { clearTimeout(timer); void load(); });
    async function load(next = 1) {
        const revision = ++read;
        message.textContent = 'Đang tải…';
        body.querySelectorAll('button').forEach(b => b.disabled = true);
        try {
            const q = new URLSearchParams({ page: String(next) });
            logRange(section, q);
            if (actor.value)
                q.set('actorId', actor.value);
            if (action.value)
                q.set('action', action.value);
            if (search.value.trim())
                q.set('search', search.value.trim());
            const r = await api('admin/audit?' + q);
            if (revision !== read)
                return;
            page = r.page;
            body.innerHTML = renderAuditReport(r);
            message.textContent = '';
            const previousActor = actor.value, previousAction = action.value;
            actor.innerHTML = '<option value="">Tất cả</option>' + r.actors.map(i => `<option value="${esc(i.id)}">${esc(i.name)}</option>`).join('');
            actor.value = previousActor;
            action.innerHTML = '<option value="">Tất cả</option>' + r.actions.map(i => `<option value="${esc(i)}">${esc(auditLabels[i] ?? i)}</option>`).join('');
            action.value = previousAction;
        }
        catch (e) {
            if (revision !== read)
                return;
            body.innerHTML = '';
            message.textContent = e instanceof Error ? e.message : 'Chưa đọc được nhật ký quản trị.';
        }
    }
    section.addEventListener('change', () => { clearTimeout(timer); void load(); });
    search.addEventListener('input', () => { ++read; clearTimeout(timer); timer = setTimeout(() => void load(), 250); });
    section.querySelector('[data-audit-refresh]').addEventListener('click', () => void load(page));
    section.addEventListener('click', e => { const b = e.target.closest('button'); if (!b || b.disabled)
        return; if (b.dataset.auditPage)
        void load(Number(b.dataset.auditPage)); if (b.dataset.auditDetail)
        void open(b.dataset.auditDetail); });
    async function open(id) { if (opening || root.querySelector('.admin-log-dialog'))
        return; opening = true; const { dialog, body } = logDialog(root, 'Chi tiết thao tác quản trị'); try {
        const r = await api('admin/audit/' + id);
        if (dialog.isConnected)
            body.innerHTML = renderAuditDetail(r);
    }
    catch (e) {
        if (dialog.isConnected)
            body.textContent = e instanceof Error ? e.message : 'Chưa đọc được chi tiết.';
    }
    finally {
        opening = false;
    } }
    root.addEventListener('qd766-log-view', e => { if (e.detail === 'audit')
        void load(page);
    else {
        ++read;
        clearTimeout(timer);
    } });
}
//# sourceMappingURL=admin-audit-log.js.map