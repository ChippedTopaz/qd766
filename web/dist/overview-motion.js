let running = [];
let cleanupTimer = null;
let cleanupListeners = null;
const duration = 900;
const selector = '[data-overview-layout] [data-motion-card]';
let detailMotion = null;
export function cancelOverviewMotion() {
    if (detailMotion) {
        detailMotion.out?.cancel();
        detailMotion.incoming.cancel();
        detailMotion.old?.remove();
        detailMotion = null;
    }
    if (cleanupTimer !== null) {
        clearTimeout(cleanupTimer);
        cleanupTimer = null;
    }
    cleanupListeners?.();
    cleanupListeners = null;
    for (const item of running) {
        item.animation.cancel();
        item.content.cancel();
        item.labelAnimation.cancel();
        item.surface.remove();
        item.label.remove();
        item.target.style.removeProperty('opacity');
    }
    running = [];
    document.querySelectorAll('.overview-motion-content').forEach(el => el.classList.remove('overview-motion-content'));
}
/** Move only the detail body; the selected tile updates immediately. */
export function transitionDetail(update, nextKey) {
    const strip = document.querySelector('.overview-score-strip');
    const keys = Array.from(strip?.querySelectorAll('[data-motion-card]') ?? []).map(el => el.dataset.motionCard);
    const current = strip?.querySelector('[aria-pressed="true"]')?.dataset.motionCard;
    const source = document.querySelector('[data-overview-content]');
    const animate = !!source && !!strip && current !== nextKey && keys.includes(nextKey) &&
        !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches && typeof source.animate === 'function';
    const mobile = window.matchMedia?.('(max-width: 600px)').matches;
    const direction = keys.indexOf(nextKey) > keys.indexOf(current) ? 1 : -1;
    const rect = source?.getBoundingClientRect();
    // Outgoing copy is decorative, inert, and carries no IDs or app action selectors.
    const old = animate && !mobile ? source.cloneNode(true) : null;
    if (old) {
        for (const el of [old, ...Array.from(old.querySelectorAll('*'))]) {
            for (const attribute of Array.from(el.attributes))
                if (attribute.name === 'id' || attribute.name.startsWith('data-'))
                    el.removeAttribute(attribute.name);
        }
        old.className = 'overview-detail-outgoing';
        old.setAttribute('aria-hidden', 'true');
        old.setAttribute('inert', '');
    }
    cancelOverviewMotion();
    update();
    const target = document.querySelector('[data-overview-content]');
    if (!animate || !target || typeof target.animate !== 'function')
        return;
    const distance = mobile ? 0 : 48 * direction;
    let out = null;
    if (old && rect) {
        Object.assign(old.style, { position: 'fixed', left: rect.left + 'px', top: rect.top + 'px', width: rect.width + 'px',
            height: Math.max(0, Math.min(rect.height, window.innerHeight - rect.top)) + 'px', overflow: 'hidden', pointerEvents: 'none' });
        document.body.append(old);
        out = old.animate([{ opacity: 1, transform: 'translateX(0)' }, { opacity: 0, transform: `translateX(${-distance}px)` }], { duration: 240, easing: 'ease-in', fill: 'both' });
    }
    const incoming = target.animate([{ opacity: 0, transform: `translateX(${distance}px)` }, { opacity: 1, transform: 'translateX(0)' }], { duration: mobile ? 260 : 520, delay: mobile ? 0 : 80, easing: 'cubic-bezier(.4,0,.2,1)', fill: 'both' });
    detailMotion = { old, out, incoming };
    cleanupTimer = setTimeout(cancelOverviewMotion, mobile ? 290 : 630);
    const stop = () => cancelOverviewMotion();
    window.addEventListener('resize', stop, { once: true });
    window.addEventListener('scroll', stop, { once: true });
    cleanupListeners = () => { window.removeEventListener('resize', stop); window.removeEventListener('scroll', stop); };
}
export function transitionOverview(update) {
    const layout = document.querySelector('[data-overview-layout]')?.dataset.overviewLayout;
    const frames = Array.from(document.querySelectorAll(selector)).map(node => {
        const active = running.find(item => item.target.dataset.motionCard === node.dataset.motionCard);
        const title = node.querySelector('.pillar-heading h3,.bento-card-head h2,:scope > span');
        return { key: node.dataset.motionCard, rect: (active?.surface ?? node).getBoundingClientRect(),
            title: active?.label.getBoundingClientRect() ?? title?.getBoundingClientRect() ?? null };
    });
    cancelOverviewMotion();
    update();
    const next = document.querySelector('[data-overview-layout]')?.dataset.overviewLayout;
    if (!layout || !next || layout === next || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)
        return;
    const targets = Array.from(document.querySelectorAll(selector));
    if (!targets.length || typeof targets[0].animate !== 'function')
        return;
    for (const target of targets) {
        const source = frames.find(frame => frame.key === target.dataset.motionCard);
        const to = target.getBoundingClientRect();
        if (!source || !to.width || !to.height || source.rect.bottom < 0 || to.right < 0 || to.left >= window.innerWidth)
            continue;
        const surface = document.createElement('div');
        surface.className = 'overview-motion-surface';
        surface.setAttribute('aria-hidden', 'true');
        const style = getComputedStyle(target);
        Object.assign(surface.style, { position: 'fixed', left: to.left + 'px', top: to.top + 'px', width: to.width + 'px', height: to.height + 'px',
            background: style.background, border: style.border, borderRadius: style.borderRadius, boxShadow: style.boxShadow,
            transformOrigin: '0 0', pointerEvents: 'none' });
        document.body.append(surface);
        const from = `translate(${source.rect.left - to.left}px,${source.rect.top - to.top}px) scale(${source.rect.width / to.width},${source.rect.height / to.height})`;
        const animation = surface.animate([{ transform: from, opacity: 1 }, { transform: 'translate(0,0) scale(1,1)', opacity: 0 }], { duration, easing: 'cubic-bezier(.4,0,.2,1)', fill: 'both' });
        target.style.opacity = '0';
        // Animate opacity only on content: never scale glyphs or the gauge drawing.
        const content = target.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 380, delay: 450, easing: 'ease-out', fill: 'both' });
        const title = target.querySelector('.pillar-heading h3,.bento-card-head h2,:scope > span');
        const label = document.createElement('span');
        label.className = 'overview-motion-label';
        label.setAttribute('aria-hidden', 'true');
        label.textContent = title?.textContent ?? '';
        const titleRect = title?.getBoundingClientRect() ?? to, titleStyle = title ? getComputedStyle(title) : style;
        Object.assign(label.style, { left: titleRect.left + 'px', top: titleRect.top + 'px', width: titleRect.width + 'px',
            color: titleStyle.color, font: titleStyle.font, lineHeight: titleStyle.lineHeight, textAlign: titleStyle.textAlign });
        document.body.append(label);
        const start = source.title ?? source.rect;
        const labelAnimation = label.animate([
            { transform: `translate(${start.left - titleRect.left}px,${start.top - titleRect.top}px)`, opacity: .8 },
            { transform: 'translate(0,0)', opacity: 0 }
        ], { duration: duration - 30, easing: 'cubic-bezier(.4,0,.2,1)', fill: 'both' });
        running.push({ surface, target, animation, content, label, labelAnimation });
    }
    document.querySelector('[data-overview-content]')?.classList.add('overview-motion-content');
    cleanupTimer = setTimeout(cancelOverviewMotion, duration + 30);
    // Fixed motion surfaces must not float over content when the viewport moves.
    const stop = () => cancelOverviewMotion();
    window.addEventListener('resize', stop, { once: true });
    window.addEventListener('scroll', stop, { once: true });
    cleanupListeners = () => { window.removeEventListener('resize', stop); window.removeEventListener('scroll', stop); };
}
//# sourceMappingURL=overview-motion.js.map