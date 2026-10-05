import {dailyChanges,type DailyHistory} from './daily-history.js';
import {changeTone} from './change-tone.js';
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const num=(v:number)=>v.toLocaleString('vi-VN',{minimumFractionDigits:2,maximumFractionDigits:2});
const date=(v:string)=>v.split('-').reverse().join('/');

/** Only the annual overview hero uses daily observations. Gauge stays latest. */
export function annualDailyComparison(history:DailyHistory|null,selectedDate?:string,loading=false,error=''):string{
  const days=[...(history?.days??[])].sort((a,b)=>b.reportDate.localeCompare(a.reportDate));
  const selected=days.find(day=>day.reportDate===selectedDate)??days[0];
  const change=dailyChanges(selected?days.filter(day=>day.reportDate<=selected.reportDate):[]);
  const options=days.map(day=>`<option value="${esc(day.reportDate)}" ${day===selected?'selected':''}>${esc(date(day.reportDate))}</option>`).join('');
  const status=loading?'Đang tải…':error?'Chưa đọc được dữ liệu':!selected?'Chưa có lịch sử ngày':change.points===null?'Chưa có ngày liền trước':`${change.points>0?'+':''}${num(change.points)} điểm`;
  return `<div class="annual-daily-comparison"><span>So với ngày trước</span><label class="annual-date-control"><span class="sr-only">Ngày quan sát điểm năm</span><select data-annual-observation aria-label="Ngày quan sát điểm năm" ${!days.length?'disabled':''}>${options||'<option>Chưa có ngày quan sát</option>'}</select></label><strong class="${changeTone(change.points)}">${esc(status)}</strong><small>${selected?`Điểm ngày chọn: ${selected.totalScore==null?'—':num(selected.totalScore)} · Tham khảo`:'Biến động điểm năm · Tham khảo'}</small>${error?'<button class="annual-retry" data-daily-refresh>Thử lại</button>':''}</div>`;
}
