import { personalCreditMarkup, CREDIT_PAGE_SIZE } from "./personal-credit-view.js";
const num = (n) => new Intl.NumberFormat("vi-VN").format(n);
const esc = (v) => v.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export function requestCreditDisplay(state, cost) {
    if (cost === null)
        return "Quản trị";
    if (state === "ready" || state === "succeeded")
        return `<span style="color:#dc2626;font-variant-numeric:tabular-nums">-${num(cost)}</span>`;
    return `<span style="font-variant-numeric:tabular-nums" ${["waiting", "reserved", "queued", "running"].includes(state) ? `title="Đang giữ ${num(cost)} credit; chưa ghi nhận thu"` : ""}>0</span>`;
}
export function openPersonalCredits(onBalance) {
    if (document.querySelector('.personal-credits-dialog'))
        return;
    const previous = document.activeElement, dialog = document.createElement('dialog');
    dialog.className = 'personal-credits-dialog';
    dialog.setAttribute('aria-label', 'Credit của tôi');
    let offset = 0, tab = 'general', data = null, loading = false, error = '', redemptionToken = null, renewing = false;
    document.body.append(dialog);
    dialog.addEventListener('close', () => { dialog.remove(); if (previous?.isConnected)
        previous.focus(); }, { once: true });
    dialog.showModal();
    function draw() {
        if (!dialog.isConnected)
            return;
        dialog.innerHTML = personalCreditMarkup(data, tab, offset, loading, error);
        dialog.querySelector('[data-close]')?.addEventListener('click', () => dialog.close());
        dialog.querySelectorAll('[data-credit-tab]').forEach(el => el.addEventListener('click', () => { tab = el.dataset.creditTab === 'history' ? 'history' : 'general'; draw(); }));
        dialog.querySelector('[data-retry]')?.addEventListener('click', () => void load(offset));
        dialog.querySelector('[data-prev]')?.addEventListener('click', () => { if (!loading && offset > 0)
            void load(Math.max(0, offset - CREDIT_PAGE_SIZE)); });
        dialog.querySelector('[data-next]')?.addEventListener('click', () => { if (!loading && data && offset + CREDIT_PAGE_SIZE < data.total)
            void load(offset + CREDIT_PAGE_SIZE); });
        const confirm = dialog.querySelector('[data-renew-confirm]');
        dialog.querySelector('[data-renew]')?.addEventListener('click', () => { if (confirm && data?.canRedeem)
            confirm.hidden = false; });
        dialog.querySelector('[data-cancel-renew]')?.addEventListener('click', () => { if (confirm)
            confirm.hidden = true; });
        dialog.querySelector('[data-confirm-renew]')?.addEventListener('click', async (event) => {
            if (renewing || !data?.canRedeem)
                return;
            renewing = true;
            const button = event.currentTarget;
            button.disabled = true;
            const status = dialog.querySelector('[data-renew-status]'), wallet = data;
            try {
                const me = await fetch('/api/v1/auth/me', { cache: 'no-store' });
                if (!me.ok)
                    throw new Error('Phiên đăng nhập đã hết hạn.');
                const profile = await me.json();
                redemptionToken ??= crypto.randomUUID();
                const response = await fetch('/api/v1/me/subscription/redemption', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-QD766-CSRF': profile.csrfToken }, body: JSON.stringify({ token: redemptionToken, expectedCost: wallet.redemptionCost }) });
                const result = await response.json();
                if (!response.ok)
                    throw new Error('Chưa thể gia hạn. Vui lòng kiểm tra thời hạn sử dụng và Credit bổ sung.');
                redemptionToken = null;
                onBalance?.(result.availableCredits, wallet.reservedCredits);
                await load(0);
                const done = dialog.querySelector('[data-renew-status]');
                if (done)
                    done.textContent = 'Gia hạn thành công.';
            }
            catch (e) {
                if (status?.isConnected)
                    status.textContent = e instanceof Error ? e.message : 'Không thể gia hạn.';
                button.disabled = false;
            }
            finally {
                renewing = false;
            }
        });
    }
    async function load(nextOffset) {
        if (loading)
            return;
        loading = true;
        error = '';
        draw();
        try {
            const response = await fetch('/api/v1/me/credits?offset=' + nextOffset + '&limit=' + CREDIT_PAGE_SIZE, { cache: 'no-store' });
            if (!response.ok)
                throw new Error('Không thể tải thông tin Credit. Vui lòng thử lại.');
            const result = await response.json();
            if (!dialog.isConnected)
                return;
            data = result;
            offset = nextOffset;
        }
        catch (e) {
            error = e instanceof Error ? e.message : 'Không thể tải thông tin Credit.';
        }
        finally {
            loading = false;
            draw();
        }
    }
    void load(0);
}
//# sourceMappingURL=personal-credits.js.map