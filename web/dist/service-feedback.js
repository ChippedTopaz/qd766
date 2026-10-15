export const serviceCopy = {
    unavailable: { title: 'Dịch vụ tạm thời gián đoạn', message: 'Chúng tôi chưa thể tải nội dung vào lúc này. Vui lòng thử lại sau ít phút.' },
    offline: { title: 'Kết nối Internet bị gián đoạn', message: 'Vui lòng kiểm tra kết nối mạng của thiết bị, sau đó thử lại để tiếp tục.' },
    slow: { title: 'Phản hồi chậm hơn dự kiến', message: 'Kết nối chưa hoàn tất. Vui lòng thử lại sau ít phút.' },
    session: { title: 'Phiên làm việc đã kết thúc', message: 'Vui lòng đăng nhập lại để tiếp tục sử dụng hệ thống.' },
    refresh: { title: 'Phiên làm việc đã được cập nhật', message: 'Vui lòng tải lại trang để đồng bộ phiên làm việc và tiếp tục.' },
    access: { title: 'Chưa thể truy cập nội dung này', message: 'Tài khoản hiện tại chưa có quyền truy cập nội dung này. Vui lòng liên hệ quản trị viên nếu cần hỗ trợ.' },
    missing: { title: 'Nội dung chưa sẵn sàng', message: 'Nội dung bạn tìm chưa có hoặc không còn khả dụng. Bạn có thể quay về trang chủ để tiếp tục.' },
};
export class ServiceError extends Error {
    kind;
    status;
    constructor(kind, status = 0) {
        super(serviceCopy[kind].message);
        this.kind = kind;
        this.status = status;
        this.name = 'ServiceError';
    }
}
const technical = /(?:failed to fetch|fetch failed|network\s?error|load failed|network request failed|illegal invocation|unexpected token|unexpected end|json|internal server error|bad gateway|service unavailable|gateway time.?out|backend|https? máy|máy chủ cục bộ|postgreSQL|sqlite|traceback|sqlalchemy|\bHTTP\s*\d{3}\b|ECONN\w*|ENOTFOUND|<\/?(?:html|script|body|img)\b)/i;
const offline = () => typeof navigator !== 'undefined' && navigator.onLine === false;
export function serviceStateFor(error) {
    if (error instanceof ServiceError)
        return error.kind === 'unavailable' && offline() ? 'offline' : error.kind;
    if (offline())
        return 'offline';
    const text = error instanceof Error ? error.message : String(error ?? '');
    if (/timeout|timed? out/i.test(text) || (error instanceof Error && ['TimeoutError', 'AbortError'].includes(error.name)))
        return 'slow';
    return 'unavailable';
}
/** Keep actionable business/validation messages; never print raw infrastructure errors. */
export function userFacingError(error, fallback = 'Chưa thể hoàn tất thao tác. Vui lòng thử lại sau ít phút.') {
    if (error instanceof ServiceError)
        return serviceCopy[serviceStateFor(error)].message;
    if (error instanceof Error && ['TimeoutError', 'AbortError'].includes(error.name))
        return serviceCopy.slow.message;
    const message = error instanceof Error ? error.message : typeof error === 'string' ? error : '';
    if (technical.test(message) || error instanceof SyntaxError)
        return serviceCopy[serviceStateFor(error)].message;
    if (offline() && error instanceof TypeError)
        return serviceCopy.offline.message;
    if (message && /[À-ỹĐđ]/.test(message) && !/[<>\u0000-\u0008]/.test(message))
        return message;
    return fallback;
}
/** Non-JSON error pages are expected when an upstream service is unavailable. */
export async function readServiceJson(response) {
    if (response.status === 401)
        throw new ServiceError('session', 401);
    if (response.status >= 500)
        throw new ServiceError('unavailable', response.status);
    let body;
    try {
        body = await response.json();
    }
    catch {
        throw new ServiceError(response.status === 403 ? 'access' : response.status === 404 ? 'missing' : 'unavailable', response.status);
    }
    if (response.ok)
        return body;
    const detail = typeof body?.detail === 'string' ? body.detail : '';
    if (response.status === 403 && detail === 'Xác nhận phiên không hợp lệ.')
        throw new ServiceError('refresh', 403);
    if (detail && !technical.test(detail) && /[À-ỹĐđ]/.test(detail) && !/[<>]/.test(detail))
        throw new Error(detail);
    throw new ServiceError(response.status === 403 ? 'access' : response.status === 404 ? 'missing' : 'unavailable', response.status);
}
const styles = `
.service-state-page{min-height:85svh;box-sizing:border-box;display:grid;place-items:center;padding:40px 24px;background:radial-gradient(ellipse at 15% 15%,#e9eaff80,transparent 60%),#f5f7fe;color:#132447;font-family:Inter,"Segoe UI",sans-serif}
.service-state-shell{width:min(920px,100%);min-width:0}.service-state-brand{display:flex;align-items:center;gap:10px;color:#243961;font-size:14px;font-weight:700;margin-bottom:28px;text-decoration:none}.service-state-brand img{width:36px;height:36px;object-fit:contain}
.service-state-card{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);align-items:center;gap:36px;padding:48px;background:#fff;border:1px solid #e7ebf5;border-radius:24px;box-shadow:0 18px 60px -32px #26346240}
.service-state-art{width:100%;max-width:280px;justify-self:center;display:block}.service-state-copy{min-width:0}.service-state-eyebrow{font-size:11px;letter-spacing:1.3px;color:#6964b4;font-weight:700;margin:0 0 12px}.service-state-copy h1,.service-state-copy h2{font-size:clamp(22px,2.5vw,28px);line-height:1.35;letter-spacing:-.5px;margin:0 0 14px;color:#14284d}.service-state-copy>p:not(.service-state-eyebrow){font-size:14px;line-height:1.8;color:#63728b;margin:0}
.service-state-actions{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:26px}.service-state-actions button,.service-state-actions a{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:42px;box-sizing:border-box;border-radius:11px;padding:10px 18px;font-size:13px;font-weight:650;line-height:1.4;text-decoration:none;cursor:pointer;font-family:inherit;max-width:100%}.service-state-actions button{background:#5042e9;color:#fff;border:1px solid #5042e9}.service-state-actions button:hover{background:#4334d4}.service-state-actions button:disabled{opacity:.7;cursor:wait}.service-state-actions a{background:#fff;color:#475b7c;border:1px solid #dfe5f0}.service-state-actions svg{width:16px;height:16px}.service-state-actions :focus-visible{outline:3px solid #a5b4fc;outline-offset:4px}.service-state-foot{font-size:12px;color:#7c89a1;margin:22px 0 0;line-height:1.7;text-align:center}
.service-state-compact{padding:24px;background:transparent;min-height:0}.service-state-compact .service-state-brand,.service-state-compact .service-state-foot{display:none}.service-state-compact .service-state-card{padding:28px;gap:24px;box-shadow:none;grid-template-columns:150px minmax(0,1fr)}.service-state-compact .service-state-copy h2{font-size:21px}
@media(max-width:640px){.service-state-page{padding:24px 16px;min-height:80svh}.service-state-brand{margin-bottom:20px}.service-state-card{grid-template-columns:1fr;gap:20px;padding:28px 24px;border-radius:20px}.service-state-art{max-width:180px}.service-state-actions{margin-top:22px}.service-state-copy h1,.service-state-copy h2{font-size:23px}.service-state-compact{min-height:0;padding:12px}.service-state-compact .service-state-card{grid-template-columns:1fr;padding:24px}.service-state-compact .service-state-art{max-width:130px}}
`;
const illustration = `<svg class="service-state-art" viewBox="0 0 300 230" fill="none" aria-hidden="true" focusable="false"><ellipse cx="149" cy="205" rx="112" ry="12" fill="#f0f2fb"/><circle cx="148" cy="112" r="98" fill="#f5f5ff"/><circle cx="242" cy="46" r="8" fill="#e0e7ff"/><circle cx="43" cy="160" r="5" fill="#c7d2fe"/><path d="M41 77h22m-11-11v22M247 148h15m-7-7v14" stroke="#c7d2fe" stroke-width="2" stroke-linecap="round"/><rect x="57" y="58" width="184" height="130" rx="16" fill="white" stroke="#dce2f4" stroke-width="2"/><path d="M58 86h182" stroke="#e8ecf7" stroke-width="2"/><circle cx="73" cy="72" r="3" fill="#a5b4fc"/><circle cx="84" cy="72" r="3" fill="#c7d2fe"/><circle cx="95" cy="72" r="3" fill="#e0e7ff"/><rect x="77" y="105" width="40" height="61" rx="8" fill="#eef2ff"/><path d="M88 153v-15m10 15v-28m10 28v-20" stroke="#a5b4fc" stroke-width="5" stroke-linecap="round"/><rect x="132" y="110" width="83" height="7" rx="3.5" fill="#e0e7ff"/><rect x="132" y="128" width="65" height="6" rx="3" fill="#edf0f9"/><rect x="132" y="145" width="75" height="6" rx="3" fill="#edf0f9"/><circle cx="232" cy="169" r="29" fill="#fff" stroke="#e3e6f5" stroke-width="2"/><path d="M217 163a21 21 0 0 1 30 0m-25 6a14 14 0 0 1 20 0m-15 6a7 7 0 0 1 10 0" stroke="#7064dc" stroke-width="2.5" stroke-linecap="round"/><circle cx="232" cy="181" r="2" fill="#7064dc"/><circle cx="252" cy="147" r="10" fill="#fff7ed" stroke="#ffdfb4"/><path d="M252 142v6m0 3v.5" stroke="#c78932" stroke-width="2" stroke-linecap="round"/></svg>`;
export function renderServiceState(error, options = {}) {
    const named = typeof error === 'string' && Object.hasOwn(serviceCopy, error);
    const kind = named ? error : serviceStateFor(error);
    const base = serviceCopy[kind], message = named ? base.message : userFacingError(error, base.message);
    const copy = { title: message === base.message ? base.title : 'Chưa thể hoàn tất yêu cầu', message: message.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])) }, heading = options.compact ? 'h2' : 'h1';
    return `<style>${styles}</style><section class="service-state-page${options.compact ? ' service-state-compact' : ''}" aria-label="Thông báo dịch vụ"><div class="service-state-shell"><a class="service-state-brand" href="/"><img src="/assets/logo-cchc.png" alt="" width="36" height="36">Bộ chỉ số 766</a><div class="service-state-card">${illustration}<div class="service-state-copy"><p class="service-state-eyebrow">BỘ CHỈ SỐ 766</p><${heading} tabindex="-1" data-service-heading>${copy.title}</${heading}><p role="status">${copy.message}</p><div class="service-state-actions">${kind === 'session' ? '<a href="/" data-service-login>Đăng nhập lại</a>' : `<button type="button" data-service-retry><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"/></svg>${kind === 'refresh' ? 'Tải lại trang' : 'Thử lại'}</button>`}${options.admin || kind === 'access' || kind === 'missing' ? '<a href="/">Về trang chủ</a>' : ''}</div></div></div><p class="service-state-foot">Cần thêm trợ giúp? Vui lòng liên hệ bộ phận hỗ trợ của hệ thống.</p></div></section>`;
}
export function bindServiceRetry(root, reload = () => location.reload()) {
    root.querySelectorAll('[data-service-retry]').forEach(button => button.addEventListener('click', () => { if (button.disabled)
        return; button.disabled = true; button.textContent = 'Đang tải lại…'; reload(); }, { once: true }));
}
//# sourceMappingURL=service-feedback.js.map