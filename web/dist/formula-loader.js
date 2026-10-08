import { setFormulaConfiguration } from './formula-reference.js';
let pending = null, lastLoaded = 0;
// Lazy load only on the reference screen; no impact on dashboard startup.
export function loadFormulaConfiguration() {
    if (pending)
        return pending;
    if (Date.now() - lastLoaded < 10000)
        return Promise.resolve(false);
    pending = (async () => {
        const response = await fetch('/api/v1/formula-reference', { cache: 'no-store', signal: AbortSignal.timeout(12000) });
        if (!response.ok)
            throw new Error('Không tải được nội dung Công thức tính mới nhất.');
        const value = await response.json();
        setFormulaConfiguration(value.configuration);
        lastLoaded = Date.now();
        return true;
    })().finally(() => { pending = null; });
    return pending;
}
//# sourceMappingURL=formula-loader.js.map