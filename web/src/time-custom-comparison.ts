import type {GroupId} from './types.js';
import {changeTone} from './change-tone.js';
export type ComparisonKind='day'|'month'|'quarter'|'year';
export interface ComparisonRow {label:string;total:number|null;rank:string;groups:Partial<Record<GroupId,number|null>>;provisional?:boolean;chronology?:number;periodId?:string;reportDate?:string}
export const comparisonEscape=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const n=(v:number|null|undefined)=>v==null?'—':v.toLocaleString('vi-VN',{minimumFractionDigits:2,maximumFractionDigits:2});
export function customComparisonTable(current:ComparisonRow,baseline:ComparisonRow,groups:GroupId[],labels:Record<GroupId,string>,renderPoint?:(row:ComparisonRow,group:GroupId|null,value:number|null|undefined)=>string){
 const newerIndex=Number.isFinite(current.chronology)&&Number.isFinite(baseline.chronology)&&(baseline.chronology??0)>(current.chronology??0)?1:0;
 const rows=[current,baseline],newer=rows[newerIndex]!,older=rows[1-newerIndex]!;
 const difference=(a:number|null|undefined,b:number|null|undefined)=>a!=null&&b!=null?a-b:null;
 const delta=difference(newer.total,older.total);
 const point=(row:ComparisonRow,group:GroupId|null,value:number|null|undefined)=>renderPoint?renderPoint(row,group,value):n(value);
 return `<div class="table-wrap"><table><thead><tr><th>Kỳ</th><th>Tổng điểm</th><th>Điểm kỳ trước</th><th>Tăng/giảm điểm</th><th>Thứ hạng</th>${groups.map(g=>`<th>${comparisonEscape(labels[g])}</th>`).join('')}</tr></thead><tbody>${rows.map((row,i)=>{
  const isNewer=i===newerIndex;
  return `<tr><td>${comparisonEscape(row.label)} <span class="badge">${i?'Mốc':'So sánh'}</span>${row.provisional?' <span class="badge warn">Tạm thời</span>':''}</td><td class="num ${isNewer?changeTone(delta):''}">${point(row,null,row.total)}</td><td class="num">${isNewer?point(older,null,older.total):'—'}</td><td class="num ${isNewer?changeTone(delta):''}">${!isNewer||delta==null?'—':(delta>=0?'+':'')+n(delta)}</td><td class="num">${comparisonEscape(row.rank)}</td>${groups.map(g=>`<td class="num ${isNewer?changeTone(difference(row.groups[g],older.groups[g])):''}">${point(row,g,row.groups[g])}</td>`).join('')}</tr>`;
 }).join('')}</tbody></table></div>`;
}
