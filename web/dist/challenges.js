import { userFacingError, readServiceJson } from './service-feedback.js';
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let context = '', directory = [], items = [], eligible = false, loaded = false, loading = false, busy = false, message = '', query = '', agencyId = '', recipientId = '', kind = 'month';
let historyPage = 1, historyTotal = 0;
export function challengePagination(page, total, attribute) {
    const pages = Math.max(1, Math.ceil(total / 10));
    return total ? `<nav class="challenge-pagination" aria-label="Phân trang kèo"><span>Trang ${page}/${pages} · ${total} kèo</span><div><button type="button" class="btn small" ${attribute}="${page - 1}" ${page <= 1 ? 'disabled' : ''}>Trước</button><button type="button" class="btn small" ${attribute}="${page + 1}" ${page >= pages ? 'disabled' : ''}>Sau</button></div></nav>` : '';
}
function setHistory(r) { items = r.items; historyPage = r.page ?? 1; historyTotal = r.total ?? r.items.length; }
const localParts = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: 'numeric', day: 'numeric' }).formatToParts(new Date());
const today = () => { const p = localParts(); return { year: Number(p.find(x => x.type === 'year').value), month: Number(p.find(x => x.type === 'month').value) }; };
let year = today().year, value = today().month;
export function periodChoices(type, y, now = today()) {
    const min = y === now.year ? (type === 'month' ? now.month : Math.ceil(now.month / 3)) : 1;
    if (y < now.year)
        return [];
    return type === 'year' ? [0] : Array.from({ length: type === 'month' ? 12 : 4 }, (_, i) => i + 1).filter(i => i >= min);
}
const period = (k) => k.periodType === 'year' ? 'Năm ' + k.year : (k.periodType === 'quarter' ? 'Quý ' : 'Tháng ') + k.periodValue + '/' + k.year;
const labels = { pending: 'Chờ chấp nhận', accepted: 'Đang diễn ra', declined: 'Đã từ chối', expired: 'Hết hạn xác nhận', 'waiting-result': 'Chờ kết quả', finished: 'Đã kết thúc' };
export function duelRows(rows, actions = false) {
    return rows.map(k => `<tr><td><strong>${esc(k.sender)}</strong><br><small>${esc(k.senderUnit)}</small></td><td><strong>${esc(k.recipient)}</strong><br><small>${esc(k.recipientUnit)}</small></td><td>${esc(period(k))}</td><td>${esc(labels[k.state] ?? k.state)}</td><td class="num">${k.senderScore == null ? '—' : esc(k.senderScore.toFixed(2))} / ${k.recipientScore == null ? '—' : esc(k.recipientScore.toFixed(2))}</td><td>${k.state === 'finished' ? (k.winnerId ? esc(k.winnerId === k.senderId ? k.sender : k.recipient) + ' thắng' : 'Hòa') : '—'}${actions && k.canAnswer ? `<div class="challenge-answer"><button type="button" class="btn small primary" data-duel-answer="${esc(k.id)}" data-duel-action="accept">Chấp nhận</button><button type="button" class="btn small" data-duel-answer="${esc(k.id)}" data-duel-action="decline">Từ chối</button></div>` : ''}</td></tr>`).join('');
}
const table = (rows, actions = false) => `<div class="table-wrap"><table><thead><tr><th>Người thách đấu</th><th>Người nhận thách đấu</th><th>Kỳ báo cáo</th><th>Trạng thái</th><th>Điểm hai cơ quan</th><th>Kết quả</th></tr></thead><tbody>${duelRows(rows, actions) || '<tr><td colspan="6">Chưa có thách đấu.</td></tr>'}</tbody></table></div>`;
export function confirmChallenge(title, person, agency, periodLabel, actionLabel, personLabel = 'Người nhận thách đấu') {
    if (document.querySelector('.challenge-confirm'))
        return Promise.resolve(false);
    const trigger = document.activeElement;
    const dialog = document.createElement('dialog');
    dialog.className = 'challenge-confirm';
    dialog.setAttribute('aria-label', title);
    dialog.innerHTML = `<div class="panel-head"><h2>${esc(title)}</h2></div><div class="panel-body"><dl><dt>${esc(personLabel)}</dt><dd>${esc(person)}</dd><dt>Cơ quan</dt><dd>${esc(agency)}</dd><dt>Kỳ báo cáo</dt><dd>${esc(periodLabel)}</dd></dl><p>Kết quả tính theo tổng điểm QĐ766 cuối kỳ.</p><div class="challenge-confirm-actions"><button type="button" class="btn" data-confirm-cancel>Hủy</button><button type="button" class="btn primary" data-confirm-ok>${esc(actionLabel)}</button></div></div>`;
    document.body.append(dialog);
    dialog.showModal();
    return new Promise(resolve => {
        let accepted = false;
        dialog.querySelector('[data-confirm-cancel]')?.addEventListener('click', () => dialog.close());
        dialog.querySelector('[data-confirm-ok]')?.addEventListener('click', () => { accepted = true; dialog.close(); });
        dialog.addEventListener('close', () => { dialog.remove(); if (trigger?.isConnected)
            trigger.focus(); resolve(accepted); }, { once: true });
    });
}
async function api(path, csrf = '', body) {
    const response = await fetch('/api/v1/me/challenges' + path, { cache: 'no-store', signal: AbortSignal.timeout(15000), ...(body ? { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-QD766-CSRF': csrf }, body: JSON.stringify(body) } : {}) });
    return readServiceJson(response);
}
export function challengeMarkup() {
    if (loading)
        return '<section class="panel"><div class="panel-body">Đang tải Thách đấu…</div></section>';
    const agency = directory.find(a => a.id === agencyId);
    const matches = query.trim() ? directory.filter(a => a.name.toLocaleLowerCase('vi').includes(query.trim().toLocaleLowerCase('vi'))).slice(0, 10) : [];
    const choices = periodChoices(kind, year);
    return `<section class="panel"><div class="panel-head"><div><h2>Thách đấu</h2><p>Tổng điểm QĐ766 cuối kỳ · Thắng 3 · Hòa 1 · Thua 0</p></div><button class="btn small" data-duel-refresh>Làm mới</button></div><div class="panel-body">
 ${message ? `<p role="status">${esc(message)}</p>` : ''}
 ${eligible ? `<form data-duel-form class="challenge-form"><div class="challenge-people"><label><strong>Chọn cơ quan cùng tỉnh</strong><input type="search" data-duel-search placeholder="Nhập tên cơ quan…" value="${esc(query || agency?.name || '')}" title="${esc(agency?.name ?? '')}"></label>
 ${matches.length ? `<div class="challenge-matches">${matches.map(a => `<button type="button" class="btn small" data-duel-agency="${esc(a.id)}">${esc(a.name)}</button>`).join('')}</div>` : ''}
 <label><strong>Người nhận thách đấu</strong><select data-duel-recipient required title="${esc(agency?.users.find(u => u.id === recipientId)?.name ?? '')}" ${agency ? '' : 'disabled'}><option value="">${agency ? 'Chọn người nhận thách đấu' : 'Chọn cơ quan trước'}</option>${agency?.users.map(u => `<option value="${esc(u.id)}" ${u.id === recipientId ? 'selected' : ''}>${esc(u.name)}</option>`).join('') ?? ''}</select></label></div>
 <div class="challenge-period"><label><strong>Loại kỳ</strong><select data-duel-kind>${['month', 'quarter', 'year'].map(t => `<option value="${t}" ${t === kind ? 'selected' : ''}>${{ month: 'Tháng', quarter: 'Quý', year: 'Năm' }[t]}</option>`).join('')}</select></label><label><strong>Năm</strong><input data-duel-year type="number" min="${today().year}" max="9998" value="${year}" required></label>${kind !== 'year' ? `<label><strong>Kỳ báo cáo</strong><select data-duel-value>${choices.map(v => `<option value="${v}" ${v === value ? 'selected' : ''}>${kind === 'month' ? 'Tháng' : 'Quý'} ${v}</option>`).join('')}</select></label>` : ''}</div>
 <button type="submit" class="btn primary" ${busy || !recipientId ? 'disabled' : ''}>${busy ? 'Đang gửi…' : 'Gửi thách đấu'}</button></form>` : '<p>Chỉ tài khoản được duyệt và gán cơ quan mới có thể gửi thách đấu.</p>'}
 </div>${table(items, true)}${challengePagination(historyPage, historyTotal, 'data-duel-page')}</section>`;
}
async function load(rerender) {
    if (loading)
        return;
    loading = true;
    rerender();
    const key = context;
    try {
        const [d, r] = await Promise.all([api('/directory'), api('?page=' + historyPage)]);
        if (key !== context)
            return;
        directory = d.agencies;
        eligible = d.eligible;
        setHistory(r);
        loaded = true;
        message = '';
    }
    catch (e) {
        if (key === context)
            message = userFacingError(e);
    }
    finally {
        if (key === context) {
            loading = false;
            loaded = true;
            rerender();
        }
    }
}
export function bindChallenges(key, csrf, rerender) {
    if (context !== key) {
        context = key;
        loaded = false;
        loading = false;
        directory = [];
        items = [];
        historyPage = 1;
        historyTotal = 0;
        agencyId = '';
        recipientId = '';
        query = '';
        message = '';
    }
    if (!loaded && !loading) {
        void load(rerender);
        return;
    }
    document.querySelector('[data-duel-refresh]')?.addEventListener('click', () => void load(rerender));
    document.querySelectorAll('[data-duel-page]').forEach(el => el.addEventListener('click', async () => {
        if (busy || loading || el.disabled)
            return;
        busy = true;
        const current = context;
        document.querySelectorAll('[data-duel-page]').forEach(b => b.disabled = true);
        try {
            const r = await api('?page=' + el.dataset.duelPage);
            if (current === context) {
                setHistory(r);
                message = '';
            }
        }
        catch (e) {
            if (current === context)
                message = userFacingError(e);
        }
        finally {
            if (current === context) {
                busy = false;
                rerender();
            }
        }
    }));
    document.querySelector('[data-duel-search]')?.addEventListener('focus', e => { if (agencyId && !query)
        e.target.select(); });
    document.querySelector('[data-duel-search]')?.addEventListener('input', e => { const el = e.target; query = el.value; agencyId = ''; recipientId = ''; rerender(); const next = document.querySelector('[data-duel-search]'); next?.focus(); next?.setSelectionRange(query.length, query.length); });
    document.querySelectorAll('[data-duel-agency]').forEach(el => el.addEventListener('click', () => { agencyId = el.dataset.duelAgency; recipientId = ''; query = ''; rerender(); }));
    document.querySelector('[data-duel-recipient]')?.addEventListener('change', e => { recipientId = e.target.value; rerender(); });
    document.querySelector('[data-duel-kind]')?.addEventListener('change', e => { kind = e.target.value; value = periodChoices(kind, year)[0] ?? 0; rerender(); });
    document.querySelector('[data-duel-year]')?.addEventListener('change', e => { year = Number(e.target.value); value = periodChoices(kind, year)[0] ?? 0; rerender(); });
    document.querySelector('[data-duel-value]')?.addEventListener('change', e => { value = Number(e.target.value); });
    document.querySelector('[data-duel-form]')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (busy || !recipientId)
            return;
        const agency = directory.find(a => a.id === agencyId), person = agency?.users.find(u => u.id === recipientId);
        if (!agency || !person)
            return;
        const label = kind === 'year' ? 'Năm ' + year : (kind === 'month' ? 'Tháng ' : 'Quý ') + value + '/' + year;
        busy = true;
        if (!await confirmChallenge('Xác nhận gửi thách đấu', person.name, agency.name, label, 'Gửi thách đấu')) {
            busy = false;
            return;
        }
        rerender();
        try {
            await api('', csrf, { recipientId, periodType: kind, year, periodValue: kind === 'year' ? null : value });
            setHistory(await api('?page=1'));
            message = 'Đã gửi thách đấu. Đang chờ người nhận chấp nhận.';
        }
        catch (e) {
            message = userFacingError(e);
        }
        finally {
            busy = false;
            rerender();
        }
    });
    document.querySelectorAll('[data-duel-answer]').forEach(el => el.addEventListener('click', async () => {
        const k = items.find(k => k.id === el.dataset.duelAnswer);
        if (busy || !k)
            return;
        busy = true;
        if (!await confirmChallenge(el.dataset.duelAction === 'accept' ? 'Chấp nhận thách đấu' : 'Từ chối thách đấu', k.sender, k.senderUnit, period(k), el.dataset.duelAction === 'accept' ? 'Chấp nhận' : 'Từ chối', 'Người thách đấu')) {
            busy = false;
            return;
        }
        rerender();
        try {
            await api('/' + encodeURIComponent(el.dataset.duelAnswer) + '/answer', csrf, { action: el.dataset.duelAction });
            setHistory(await api('?page=' + historyPage));
            message = 'Đã cập nhật lời thách đấu.';
        }
        catch (e) {
            message = userFacingError(e);
        }
        finally {
            busy = false;
            rerender();
        }
    }));
}
let notificationKey = '', notificationCsrf = '', notificationItems = [], notificationCount = 0, notificationTimer = null, notificationBusy = false, notificationMessage = '';
export function incomingMarkup(rows, count = rows.length) {
    if (!count)
        return '';
    return `<header><strong>${count} lời thách đấu mới</strong></header>${rows.slice(0, 3).map(k => `<article><strong>${esc(k.sender)}</strong><span>${esc(k.senderUnit)}</span><span>${esc(period(k))}</span><div class="challenge-answer"><button class="btn small primary" data-incoming-id="${esc(k.id)}" data-incoming-action="accept">Chấp nhận</button><button class="btn small" data-incoming-id="${esc(k.id)}" data-incoming-action="decline">Từ chối</button></div></article>`).join('')}${count > 3 ? '<button type="button" class="btn small" data-incoming-all>Xem tất cả lời thách đấu</button>' : ''}`;
}
let openIncoming = () => { };
function drawIncoming() {
    const button = document.querySelector('[data-challenge-board]');
    if (!button)
        return;
    let host = document.querySelector('[data-challenge-notifications]');
    if (!host) {
        button.insertAdjacentHTML('beforebegin', '<aside class="challenge-notifications" data-challenge-notifications aria-label="Lời thách đấu mới"></aside>');
        host = document.querySelector('[data-challenge-notifications]');
    }
    if (!host)
        return;
    host.hidden = notificationCount === 0;
    host.innerHTML = incomingMarkup(notificationItems, notificationCount) + (notificationMessage ? `<p role="status">${esc(notificationMessage)}</p>` : '');
    host.querySelector('[data-incoming-all]')?.addEventListener('click', () => openIncoming());
    host.querySelectorAll('[data-incoming-id]').forEach(el => el.addEventListener('click', async () => {
        const k = notificationItems.find(k => k.id === el.dataset.incomingId);
        if (notificationBusy || !k)
            return;
        const key = notificationKey, action = el.dataset.incomingAction;
        notificationBusy = true;
        if (!await confirmChallenge(action === 'accept' ? 'Chấp nhận thách đấu' : 'Từ chối thách đấu', k.sender, k.senderUnit, period(k), action === 'accept' ? 'Chấp nhận' : 'Từ chối', 'Người thách đấu')) {
            if (key === notificationKey)
                notificationBusy = false;
            return;
        }
        if (key !== notificationKey)
            return;
        notificationBusy = true;
        host.querySelectorAll('button').forEach(b => b.disabled = true);
        try {
            await api('/' + encodeURIComponent(k.id) + '/answer', notificationCsrf, { action });
            if (key !== notificationKey)
                return;
            loaded = false;
            notificationMessage = '';
            const body = await api('/incoming');
            if (key !== notificationKey)
                return;
            notificationItems = body.items;
            notificationCount = body.count;
        }
        catch (e) {
            if (key === notificationKey)
                notificationMessage = userFacingError(e);
        }
        finally {
            if (key === notificationKey) {
                notificationBusy = false;
                drawIncoming();
            }
        }
    }));
}
async function pollIncoming(key) {
    if (key !== notificationKey)
        return;
    if (!document.hidden) {
        try {
            const body = await api('/incoming');
            if (key !== notificationKey || !Array.isArray(body.items) || !Number.isInteger(body.count))
                return;
            notificationItems = body.items;
            notificationCount = body.count;
            drawIncoming();
        }
        catch { /* Keep collection and the rest of the page independent of notifications. */ }
    }
    if (key === notificationKey && typeof window.setTimeout === 'function')
        notificationTimer = window.setTimeout(() => void pollIncoming(key), 30000);
}
export function bindChallengeNotifications(key, csrf, open) {
    openIncoming = open;
    if (key !== notificationKey) {
        if (notificationTimer !== null)
            window.clearTimeout(notificationTimer);
        notificationKey = key;
        notificationCsrf = csrf;
        notificationItems = [];
        notificationCount = 0;
        notificationMessage = '';
        notificationBusy = false;
        void pollIncoming(key);
    }
    drawIncoming();
}
export async function openChallengeBoard() {
    if (document.querySelector('.challenge-board'))
        return;
    const trigger = document.activeElement;
    const dialog = document.createElement('dialog');
    dialog.className = 'challenge-board';
    dialog.setAttribute('aria-label', 'Bảng xếp hạng thách đấu');
    dialog.innerHTML = '<div class="panel-head"><h2>Bảng xếp hạng thách đấu</h2><button class="btn small" data-close>Đóng</button></div><div data-board-content class="panel-body">Đang tải…</div>';
    document.body.append(dialog);
    dialog.showModal();
    dialog.querySelector('[data-close]')?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { dialog.remove(); trigger?.focus(); }, { once: true });
    const content = dialog.querySelector('[data-board-content]');
    const pages = { active: 1, finished: 1, top: 1 };
    let sequence = 0;
    const draw = async (tab, page = pages[tab] ?? 1) => {
        const requestId = ++sequence;
        const tabs = `<div class="agency-levels">${[['active', 'Đang diễn ra'], ['finished', 'Đã kết thúc'], ['top', 'Bảng xếp hạng']].map(([id, label]) => `<button class="${id === tab ? 'active' : ''}" data-board-tab="${id}">${label}</button>`).join('')}</div>`;
        const bindTabs = () => content.querySelectorAll('[data-board-tab]').forEach(el => el.addEventListener('click', () => void draw(el.dataset.boardTab)));
        content.innerHTML = tabs + '<p role="status">Đang tải…</p>';
        bindTabs();
        try {
            const body = await api('/board?status=' + tab + '&page=' + page);
            if (!dialog.isConnected || requestId !== sequence)
                return;
            pages[tab] = body.page ?? 1;
            content.innerHTML = tabs + (tab === 'top' ? `<p>Top 20 · Thắng 3 điểm · Hòa 1 điểm · Thua 0 điểm</p><div class="table-wrap"><table><thead><tr><th>Hạng</th><th>Người chơi</th><th>Điểm</th><th>Thắng</th><th>Hòa</th><th>Thua</th></tr></thead><tbody>${body.players.map((p) => `<tr><td class="num">${esc(p.rank)}</td><td>${esc(p.name)}</td><td class="num">${esc(p.points)}</td><td class="num">${esc(p.wins)}</td><td class="num">${esc(p.draws)}</td><td class="num">${esc(p.losses)}</td></tr>`).join('') || '<tr><td colspan="6">Chưa có kết quả để xếp hạng.</td></tr>'}</tbody></table></div>` : table(body.items) + challengePagination(pages[tab] ?? 1, body.total, 'data-board-page'));
            bindTabs();
            content.querySelectorAll('[data-board-page]').forEach(el => el.addEventListener('click', () => { if (!el.disabled)
                void draw(tab, Number(el.dataset.boardPage)); }));
        }
        catch (e) {
            if (dialog.isConnected && requestId === sequence) {
                content.innerHTML = tabs + `<p role="status">${esc(userFacingError(e))}</p>`;
                bindTabs();
            }
        }
    };
    await draw('active');
}
//# sourceMappingURL=challenges.js.map