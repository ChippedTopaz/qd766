import {type DailyHistory} from './daily-history.js';
import {changeTone} from './change-tone.js';
import type {GroupId} from './types.js';
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const num=(v:number)=>v.toLocaleString('vi-VN',{minimumFractionDigits:2,maximumFractionDigits:2});
export const FIRST_DAILY_DATE='2026-10-06';
export const precedingDate=(value:string)=>new Date(Date.parse(value+'T00:00:00Z')-86400000).toISOString().slice(0,10);
export const formatDay=(value:string)=>value.split('-').reverse().join('/');
export function dailyCalendar(attribute:string,label:string,value:string,min:string,max:string,disabled=false):string{
  return `<label class="annual-date-control"><span class="sr-only">${esc(label)}</span><span class="annual-calendar"><span class="annual-calendar-date" aria-hidden="true">${value?esc(formatDay(value)):'dd/mm/yyyy'}</span><input type="date" lang="vi" ${attribute} aria-label="${esc(label)}" min="${esc(min)}" max="${esc(max)}" value="${esc(value)}" ${disabled?'disabled':''}></span></label>`;
}

export function annualObservationWindow(history:DailyHistory|null,selectedDate?:string){
  const days=[...(history?.days??[])].filter(day=>day.reportDate>=FIRST_DAILY_DATE).sort((a,b)=>b.reportDate.localeCompare(a.reportDate));
  const current=days[0];
  const baselineDate=selectedDate??(current?precedingDate(current.reportDate):'');
  const selected=current&&baselineDate<current.reportDate?days.find(day=>day.reportDate===baselineDate):undefined;
  return {days,current,selected,baselineDate};
}

/** Same observation and preceding calendar day as the overview clock. */
export function annualGroupChange(history:DailyHistory|null,groupId:GroupId,selectedDate?:string){
  const {current,selected}=annualObservationWindow(history,selectedDate);
  const a=current?.groups[groupId]?.score,b=selected?.groups[groupId]?.score;
  return a!=null&&b!=null?a-b:null;
}

/** Clock and group cards share the selected daily observation. Gauge stays latest. */
export function annualDailyComparison(history:DailyHistory|null,selectedDate?:string,loading=false,error=''):string{
  const {days,current,selected,baselineDate}=annualObservationWindow(history,selectedDate);
  const change={points:current?.totalScore!=null&&selected?.totalScore!=null?current.totalScore-selected.totalScore:null};
  const calendar=dailyCalendar('data-annual-observation','Ngày so sánh',baselineDate,FIRST_DAILY_DATE,current?precedingDate(current.reportDate):FIRST_DAILY_DATE,!days.length);
  const status=loading?'Đang tải…':error?'Chưa đọc được dữ liệu':!current?'Chưa có lịch sử ngày':change.points===null?'Chưa đủ dữ liệu ngày':`${change.points>=0?'+':''}${num(change.points)} điểm`;
  return `<div class="annual-daily-comparison"><span>So với ngày</span>${calendar}<strong class="${changeTone(change.points)}">${esc(status)}</strong><small>${current?`Dữ liệu mới nhất: ${esc(formatDay(current.reportDate))}`:'Biến động điểm năm'}${selected?` · Điểm mốc: ${selected.totalScore==null?'—':num(selected.totalScore)}`:''}</small>${error?'<button class="annual-retry" data-daily-refresh>Thử lại</button>':''}</div>`;
}
