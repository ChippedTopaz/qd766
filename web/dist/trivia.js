import { openTriviaLeaderboard } from './trivia-leaderboard.js';
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
let question = null, stats = { score: 0, streak: 0, best: 0, answered: 0 }, result = null;
let choice = null, started = false, busy = false, failed = false, message = '', available = true, roundId = '';
let deadline = 0, nextDeadline = 0, retryAt = 0, timer = null;
let mobileViewport = null;
let compactViewport = null;
let displayMode = 'normal';
const remaining = () => Math.max(0, Math.ceil((deadline - performance.now()) / 1000));
const clockText = () => result ? `Tiếp sau ${Math.max(0, Math.ceil((nextDeadline - performance.now()) / 1000))} giây` : `Còn ${remaining()} giây`;
const displayIcon = (kind) => `<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="${kind === 'minus' ? 'M4 8h8' : kind === 'plus' ? 'M4 8h8M8 4v8' : kind === 'up' ? 'M4 10l4-4 4 4' : 'M4 6l4 4 4-4'}"/></svg>`;
export function triviaMarkup() {
    const mode = compactViewport?.matches && displayMode === 'normal' ? 'minimized' : displayMode;
    if (mode === 'minimized')
        return `<section class="trivia-card trivia-minimized" aria-label="Hỏi đáp"><button type="button" class="trivia-minimized-bar" data-trivia-restore aria-label="Mở lại Hỏi đáp" title="Mở lại Hỏi đáp"><span class="trivia-bar-title">HỎI ĐÁP</span>${question ? `<span class="trivia-clock" data-trivia-clock aria-live="off">${clockText()}</span>` : ''}${displayIcon('up')}</button></section>`;
    const choices = question?.choices.map((text, i) => `<label class="${result && i === result.correctIndex ? 'trivia-correct' : ''}"><input type="radio" name="trivia-choice" value="${i}" ${choice === i ? 'checked' : ''} ${busy || result ? 'disabled' : ''}>${esc(text)}</label>`).join('');
    let body = '', actions = '';
    if (question) {
        body = `<p class="trivia-question">${esc(question.prompt)}</p><div class="trivia-choices">${choices}</div>`;
        if (result)
            body += `<p class="trivia-feedback" role="status">${result.timedOut ? 'Hết 60 giây.' : result.correct ? 'Đúng! +1 điểm.' : 'Chưa đúng.'} ${esc(result.explanation)}</p>`;
        actions = result ? `<button type="button" data-trivia-next ${busy ? 'disabled' : ''}>Câu tiếp theo</button>` :
            `<button type="button" data-trivia-submit ${busy || choice === null ? 'disabled' : ''}>${busy ? 'Đang gửi…' : 'Gửi đáp án'}</button>`;
    }
    else {
        body = `<p>${busy ? 'Đang tải câu hỏi…' : available ? 'Anh/chị đã trả lời hết Bộ câu hỏi.' : 'Ngân hàng câu hỏi chưa được mở.'}</p>`;
        if (available && roundId)
            actions += `<button type="button" data-trivia-leaderboard>Bảng xếp hạng</button><button type="button" data-trivia-restart ${busy ? 'disabled' : ''}>Trả lời lại từ đầu</button>`;
    }
    if (message)
        body += `<p role="status">${esc(message)}</p>`;
    if (failed && !result)
        actions += '<button type="button" data-trivia-next>Tải lại câu hỏi</button>';
    const controls = `<div class="trivia-display-controls"><button type="button" data-trivia-minimize aria-label="Ẩn câu hỏi" title="Ẩn câu hỏi">${displayIcon('minus')}</button><button type="button" data-trivia-expand title="${mode === 'expanded' ? 'Thu về bình thường' : 'Mở rộng câu hỏi'}" aria-label="${mode === 'expanded' ? 'Thu về bình thường' : 'Mở rộng câu hỏi'}" aria-pressed="${mode === 'expanded'}">${displayIcon(mode === 'expanded' ? 'down' : 'up')}</button></div>`;
    return `<section class="trivia-card trivia-${mode}" aria-label="Hỏi đáp"><div class="trivia-header"><h3>HỎI ĐÁP</h3>${question ? `<span class="trivia-clock" data-trivia-clock aria-live="off">${clockText()}</span>` : ''}${controls}</div><div class="trivia-stats"><span>Điểm <b>${stats.score}</b></span><span>Chuỗi đúng <b>${stats.streak}</b></span><span title="Chuỗi đúng dài nhất">Kỷ lục <b>${stats.best}</b></span></div><div class="trivia-body"><div class="trivia-body-content">${body}</div></div><div class="trivia-actions">${actions}</div></section>`;
}
function paint() { document.querySelectorAll('.trivia-card').forEach(node => { node.outerHTML = triviaMarkup(); }); }
export function bindTrivia(csrf) {
    let card = document.querySelector('.trivia-card');
    if (!card)
        return;
    if (!mobileViewport) {
        mobileViewport = window.matchMedia('(max-width:760px)');
        mobileViewport.addEventListener('change', () => bindTrivia(csrf));
    }
    if (mobileViewport.matches) {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }
        return;
    }
    if (!compactViewport) {
        compactViewport = window.matchMedia('(min-width:761px) and (max-width:1100px)');
        compactViewport.addEventListener('change', () => { paint(); bindTrivia(csrf); });
        if (compactViewport.matches) {
            paint();
            card = document.querySelector('.trivia-card');
            if (!card)
                return;
        }
    }
    const render = () => { paint(); bindTrivia(csrf); };
    card.querySelector('[data-trivia-restore]')?.addEventListener('click', () => { displayMode = compactViewport?.matches ? 'expanded' : 'normal'; render(); });
    card.querySelector('[data-trivia-leaderboard]')?.addEventListener('click', () => void openTriviaLeaderboard());
    card.querySelector('[data-trivia-minimize]')?.addEventListener('click', () => { displayMode = displayMode === 'minimized' ? 'normal' : 'minimized'; render(); });
    card.querySelector('[data-trivia-expand]')?.addEventListener('click', () => { displayMode = displayMode === 'expanded' ? 'normal' : 'expanded'; render(); });
    const load = async (restart = false) => {
        if (busy || mobileViewport?.matches)
            return;
        busy = true;
        failed = false;
        message = '';
        render();
        const requestedAt = performance.now();
        try {
            const response = await fetch('/api/v1/me/trivia' + (restart ? '/restart' : ''), restart ?
                { method: 'POST', signal: AbortSignal.timeout(15000), headers: { 'Content-Type': 'application/json', 'X-QD766-CSRF': csrf }, body: JSON.stringify({ roundId }) } :
                { cache: 'no-store', signal: AbortSignal.timeout(15000) });
            const body = await response.json();
            if (!response.ok)
                throw new Error(typeof body.detail === 'string' ? body.detail : 'Chưa tải được câu hỏi. Hãy thử lại.');
            available = body.available;
            question = body.question;
            stats = body.stats ?? stats;
            roundId = body.roundId ?? roundId;
            choice = null;
            result = null;
            nextDeadline = 0;
            deadline = question ? performance.now() + Math.max(0, Date.parse(question.expiresAt) - Date.parse(body.serverNow) - (performance.now() - requestedAt)) : 0;
            retryAt = 0;
            if (body.timedOut)
                message = 'Hết 60 giây, mất chuỗi đúng.' + (question ? ' Đã chuyển câu tiếp theo.' : '');
        }
        catch (error) {
            failed = true;
            message = error.name === 'TimeoutError' ? 'Máy chủ phản hồi chậm. Vui lòng thử lại.' : String(error.message);
            retryAt = performance.now() + 10000;
        }
        finally {
            busy = false;
            render();
        }
    };
    const tick = () => {
        if (document.hidden || mobileViewport?.matches || !question || busy)
            return;
        document.querySelectorAll('[data-trivia-clock]').forEach(node => { node.textContent = clockText(); });
        const due = result ? nextDeadline > 0 && performance.now() >= nextDeadline : remaining() === 0;
        if (due && performance.now() >= retryAt)
            void load();
    };
    if (question && !timer)
        timer = setInterval(tick, 1000);
    if (!question && timer) {
        clearInterval(timer);
        timer = null;
    }
    card.querySelectorAll('input[name=trivia-choice]').forEach(input => input.addEventListener('change', () => { choice = Number(input.value); render(); }));
    card.querySelector('[data-trivia-next]')?.addEventListener('click', () => void load());
    card.querySelector('[data-trivia-restart]')?.addEventListener('click', () => void load(true));
    card.querySelector('[data-trivia-submit]')?.addEventListener('click', async () => {
        if (busy || result || !question || choice === null)
            return;
        busy = true;
        failed = false;
        message = '';
        render();
        try {
            const response = await fetch('/api/v1/me/trivia/answer', { method: 'POST', signal: AbortSignal.timeout(15000), headers: { 'Content-Type': 'application/json', 'X-QD766-CSRF': csrf }, body: JSON.stringify({ questionId: question.id, roundId: question.roundId, choice }) });
            const body = await response.json();
            if (!response.ok)
                throw new Error(typeof body.detail === 'string' ? body.detail : 'Chưa gửi được đáp án. Hãy thử lại.');
            result = body;
            stats = body.stats;
            nextDeadline = performance.now() + 15000;
            retryAt = 0;
            if (body.timedOut) {
                busy = false;
                await load();
                message = 'Hết 60 giây, mất chuỗi đúng.' + (question ? ' Đã chuyển câu tiếp theo.' : '');
            }
        }
        catch (error) {
            failed = true;
            message = String(error.message);
        }
        finally {
            busy = false;
            render();
        }
    });
    if (!started) {
        started = true;
        document.addEventListener('visibilitychange', () => { if (!document.hidden)
            tick(); });
        void load();
    }
}
//# sourceMappingURL=trivia.js.map