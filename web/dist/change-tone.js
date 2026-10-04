/** Positive means improvement: points increase or previous rank minus current rank. */
export function changeTone(value) {
    if (value == null || !Number.isFinite(value))
        return "change-neutral";
    // Match the displayed two-decimal precision; don't color a displayed zero.
    const displayed = Math.round(Math.abs(value) * 100) / 100;
    if (displayed === 0)
        return "change-neutral";
    return value > 0 ? "change-positive" : "change-negative";
}
export function rankImprovement(previous, current) {
    return previous == null || current == null ? null : previous - current;
}
//# sourceMappingURL=change-tone.js.map