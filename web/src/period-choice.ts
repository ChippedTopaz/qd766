import type {PeriodOption} from './types.js';
/** Input ordering is not a contract: APIs/fixtures can return oldest or newest first. */
export function latestPeriod(periods:PeriodOption[]):PeriodOption|undefined{
 return [...periods].sort((a,b)=>b.year-a.year||(b.value??0)-(a.value??0))[0];
}
