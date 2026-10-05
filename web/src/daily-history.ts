import {changeTone,rankImprovement} from './change-tone.js';
import type {GroupId} from './types.js';
export interface DailyScore {reportDate:string;capturedAt:string;nationalCapturedAt:string;totalScore:number|null;rank:number|null;cohortSize:number;cohortKey:string;groups:Partial<Record<GroupId,{score:number|null;maximum:number|null}>>;peerScores?:Record<string,{totalScore:number|null;rank:number|null;groups:Partial<Record<GroupId,number|null>>}>}
export interface DailyHistory {days:DailyScore[];scope:string}
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const number=(v:number|null|undefined)=>v==null?'—':v.toLocaleString('vi-VN',{minimumFractionDigits:2,maximumFractionDigits:2});
const dayBefore=(date:string)=>new Date(Date.parse(date+'T00:00:00Z')-86400000).toISOString().slice(0,10);
export function previousDay(days:DailyScore[],day:DailyScore):DailyScore|null{return days.find(d=>d.reportDate===dayBefore(day.reportDate))??null;}
export function dailyChanges(days:DailyScore[],unitId?:string){
  const current=[...days].sort((a,b)=>b.reportDate.localeCompare(a.reportDate))[0];
  if(!current)return {points:null,rank:null,date:null};
  const previous=previousDay(days,current);
  const a=unitId?current.peerScores?.[unitId]:current,b=unitId?previous?.peerScores?.[unitId]:previous;
  const points=a?.totalScore!=null&&b?.totalScore!=null?a.totalScore-b.totalScore:null;
  const rank=previous&&current.cohortKey===previous.cohortKey?rankImprovement(b?.rank,a?.rank):null;
  return {points,rank,date:current.reportDate};
}
export function renderDailyHistory(history:DailyHistory|null,groups:GroupId[],labels:Record<GroupId,string>,error='',loading=false):string{
  if(loading)return '<section class="panel"><div class="empty-state" role="status">Đang đọc lịch sử ngày…</div></section>';
  if(error)return `<section class="panel"><div class="empty-state">${esc(error)}</div></section>`;
  const days=[...(history?.days??[])].sort((a,b)=>b.reportDate.localeCompare(a.reportDate));
  return `<section class="panel"><div class="panel-head"><div><h2>Điểm theo ngày trong kỳ</h2><p>Ngày báo cáo lấy từ đợt 02:00 sáng hôm sau. Biến động so với ngày liền trước trong cùng kỳ.</p></div></div><div class="table-wrap"><table><thead><tr><th>Ngày báo cáo</th><th>Thời điểm thu thập</th><th>Tổng điểm</th><th>Tăng/giảm điểm</th><th>Hạng</th><th>Tăng/giảm hạng</th>${groups.map(g=>`<th>${esc(labels[g])}</th>`).join('')}</tr></thead><tbody>${days.map(day=>{
    const previous=previousDay(days,day),delta=dailyChanges(days.filter(d=>d.reportDate<=day.reportDate));
    const signed=(v:number|null)=>v===null?'—':(v>0?'+':'')+number(v);
    return `<tr><td>${esc(day.reportDate.split('-').reverse().join('/'))}</td><td>${esc(new Date(day.capturedAt).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}))}</td><td class="num">${number(day.totalScore)}</td><td class="num ${changeTone(delta.points)}">${signed(delta.points)}</td><td class="num">${day.rank==null?'—':day.rank+'/'+day.cohortSize}</td><td class="num ${changeTone(delta.rank)}">${signed(delta.rank)}</td>${groups.map(g=>{
      const value=day.groups[g]?.score,prior=previous?.groups[g]?.score;
      return `<td class="num ${changeTone(value!=null&&prior!=null?value-prior:null)}">${number(value)}</td>`;
    }).join('')}</tr>`;
  }).join('')||`<tr><td colspan="${6+groups.length}">Chưa có bản lưu theo ngày của kỳ này. Lịch sử được tích lũy từ khi bật lịch 02:00.</td></tr>`}</tbody></table></div></section>`;
}
