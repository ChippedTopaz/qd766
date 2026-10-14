/** Saved-day calendar. Only available dates can be chosen; no extra requests. */
export type DateRole='baseline'|'current';
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const dayLabel=(day:string)=>day.split('-').reverse().join('/');
export function selectableDays(dates:string[],role:DateRole,other:string|null):string[]{
 return [...new Set(dates)].filter(d=>/^\d{4}-\d{2}-\d{2}$/.test(d)&&(!other||(role==='baseline'?d<other:d>other))).sort();
}
export function renderDatePicker(role:DateRole,selected:string|null,dates:string[],other:string|null):string{
 const allowed=selectableDays(dates,role,other),title=`Ngày ${role==='baseline'?'làm mốc':'đánh giá'}`;
 return `<div class="daily-date-picker" data-daily-calendar="${role}" data-calendar-dates="${esc(JSON.stringify(allowed))}">
 <strong>${title}</strong><input type="hidden" data-daily-indicator-date="${role}" value="${esc(selected??'')}">
 <button type="button" class="daily-date-open" data-calendar-open aria-haspopup="dialog" aria-expanded="false" aria-controls="daily-calendar-${role}" aria-label="${title}: ${selected?dayLabel(selected):'Chọn ngày'}" ${allowed.length?'':'disabled'}><span>${selected?dayLabel(selected):'dd/mm/yyyy'}</span><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 10h18"/></svg></button>
 <div class="daily-calendar-panel" data-calendar-panel id="daily-calendar-${role}" role="dialog" aria-label="Chọn ${title.toLowerCase()}" hidden></div></div>`;
}
export function renderCalendarMonth(month:string,dates:string[],selected:string|null):string{
 const allowed=new Set(dates),months=[...new Set(dates.map(d=>d.slice(0,7)))].sort(),years=[...new Set(months.map(m=>m.slice(0,4)))];
 const [year,value]=month.split('-').map(Number),first=new Date(Date.UTC(year!,value!-1,1)),count=new Date(Date.UTC(year!,value!,0)).getUTCDate();
 const offset=(first.getUTCDay()+6)%7;
 return `<div class="daily-calendar-heading"><button type="button" data-calendar-nav="-1" aria-label="Tháng trước có dữ liệu" ${months.indexOf(month)<=0?'disabled':''}>‹</button>
 <select data-calendar-month aria-label="Chọn tháng">${months.filter(m=>m.startsWith(String(year))).map(m=>`<option value="${m}" ${m===month?'selected':''}>Tháng ${Number(m.slice(5))}</option>`).join('')}</select>
 <select data-calendar-year aria-label="Chọn năm">${years.map(y=>`<option ${Number(y)===year?'selected':''}>${y}</option>`).join('')}</select>
 <button type="button" data-calendar-nav="1" aria-label="Tháng sau có dữ liệu" ${months.indexOf(month)>=months.length-1?'disabled':''}>›</button></div>
 <div class="daily-calendar-grid">${['T2','T3','T4','T5','T6','T7','CN'].map(d=>`<span class="daily-calendar-weekday">${d}</span>`).join('')}${'<span></span>'.repeat(offset)}${Array.from({length:count},(_,i)=>{
 const day=`${month}-${String(i+1).padStart(2,'0')}`,active=allowed.has(day);
 return `<button type="button" data-calendar-day="${day}" aria-label="${dayLabel(day)}${active?' · Có dữ liệu':' · Không thể chọn'}" aria-pressed="${day===selected}" ${active?'':'disabled'}>${i+1}</button>`;
 }).join('')}</div>`;
}
export function bindDatePickers(doc:Document):()=>void{
 const cleanups:Array<()=>void>=[],pickers=[...doc.querySelectorAll<HTMLElement>('[data-daily-calendar]')];
 pickers.forEach(root=>{
  const dates=JSON.parse(root.dataset.calendarDates!) as string[],months=[...new Set(dates.map(d=>d.slice(0,7)))].sort();
  const input=root.querySelector<HTMLInputElement>('[data-daily-indicator-date]')!,opener=root.querySelector<HTMLButtonElement>('[data-calendar-open]')!,panel=root.querySelector<HTMLElement>('[data-calendar-panel]')!;
  let month=months.includes(input.value.slice(0,7))?input.value.slice(0,7):months[months.length-1]??'';
  const close=(focus=false)=>{panel.hidden=true;opener.setAttribute('aria-expanded','false');if(focus)opener.focus();};
  const repaint=()=>{panel.innerHTML=renderCalendarMonth(month,dates,input.value);};
  opener.addEventListener('click',()=>{
   if(!dates.length)return;
   if(!panel.hidden){close();return;}
   doc.querySelectorAll<HTMLElement>('[data-calendar-panel]').forEach(p=>{p.hidden=true;});
   doc.querySelectorAll<HTMLElement>('[data-calendar-open]').forEach(b=>b.setAttribute('aria-expanded','false'));
   repaint();panel.hidden=false;opener.setAttribute('aria-expanded','true');
   panel.querySelector<HTMLButtonElement>(`[data-calendar-day="${input.value}"]:not(:disabled)`)?.focus();
   if(!panel.contains(doc.activeElement))panel.querySelector<HTMLElement>('button:not(:disabled),select')?.focus();
  });
  panel.addEventListener('click',event=>{
   const button=(event.target as Element).closest<HTMLButtonElement>('button');if(!button||button.disabled)return;
   if(button.dataset.calendarDay&&dates.includes(button.dataset.calendarDay)){
    input.value=button.dataset.calendarDay;close(true);input.dispatchEvent(new Event('change',{bubbles:true}));
   }else if(button.dataset.calendarNav){const next=months[months.indexOf(month)+Number(button.dataset.calendarNav)];if(next){month=next;repaint();panel.querySelector<HTMLButtonElement>(`[data-calendar-nav="${button.dataset.calendarNav}"]`)?.focus();}}
  });
  panel.addEventListener('change',event=>{const select=event.target as HTMLSelectElement;
   if(select.hasAttribute('data-calendar-month')&&months.includes(select.value))month=select.value;
   else if(select.hasAttribute('data-calendar-year'))month=months.find(m=>m===`${select.value}-${month.slice(5)}`)??months.find(m=>m.startsWith(select.value))??month;
   repaint();panel.querySelector<HTMLSelectElement>(select.hasAttribute('data-calendar-year')?'[data-calendar-year]':'[data-calendar-month]')?.focus();
  });
  root.addEventListener('keydown',event=>{
   if(event.key==='Escape'){event.preventDefault();close(true);return;}
   const button=(event.target as HTMLElement).closest<HTMLButtonElement>('[data-calendar-day]');
   if(button&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key)){
    event.preventDefault();const step=event.key==='ArrowLeft'?-1:event.key==='ArrowRight'?1:event.key==='ArrowUp'?-7:7;
    const day=new Date(button.dataset.calendarDay!+'T00:00:00Z');day.setUTCDate(day.getUTCDate()+step);const target=day.toISOString().slice(0,10);
    if(dates.includes(target)){month=target.slice(0,7);repaint();panel.querySelector<HTMLButtonElement>(`[data-calendar-day="${target}"]`)?.focus();}
   }
  });
  const outside=(event:Event)=>{if(!root.contains(event.target as Node))close();};
  const focusOut=(event:FocusEvent)=>{if(event.relatedTarget){if(!root.contains(event.relatedTarget as Node))close();}
   else queueMicrotask(()=>{if(!root.contains(doc.activeElement))close();});};
  doc.addEventListener('pointerdown',outside);root.addEventListener('focusout',focusOut);
  cleanups.push(()=>{doc.removeEventListener('pointerdown',outside);close();});
 });
 return ()=>cleanups.forEach(f=>f());
}
