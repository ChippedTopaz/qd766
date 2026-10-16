import type {GroupId} from './types.js';

// Presentation only: group IDs, values, formulas and source datasets stay unchanged.
const DISPLAY_ORDER:readonly GroupId[]=[
 'transparency','dvc-progress-tree','provide-online-tree',
 'formality-online-payment-tree','dossier-digitized','handling-satisfaction',
];
export function groupDisplayOrder(groups:readonly GroupId[]):GroupId[]{
 return [...groups].sort((a,b)=>DISPLAY_ORDER.indexOf(a)-DISPLAY_ORDER.indexOf(b));
}
