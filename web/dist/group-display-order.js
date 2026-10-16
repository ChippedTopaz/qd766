// Presentation only: group IDs, values, formulas and source datasets stay unchanged.
const DISPLAY_ORDER = [
    'transparency', 'dvc-progress-tree', 'provide-online-tree',
    'formality-online-payment-tree', 'dossier-digitized', 'handling-satisfaction',
];
export function groupDisplayOrder(groups) {
    return [...groups].sort((a, b) => DISPLAY_ORDER.indexOf(a) - DISPLAY_ORDER.indexOf(b));
}
//# sourceMappingURL=group-display-order.js.map