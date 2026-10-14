type Api=<T>(path:string,body?:unknown)=>Promise<T>;
type Alert={id:string;title:string;kind:string;createdAt:string;updatedAt:string;read:boolean;resolved:boolean;occurrences:number;changeCount:number;confirmed:boolean};
type Change={field:string;before:unknown;after:unknown;change:string};
type Detail=Alert&{details:{changes?:Change[];note?:string;reason?:string;confirmed?:boolean;provinceNames?:Record<string,string>;contexts?:Array<{rootId:string;rootName?:string;group:string;year:number;value:number|null;periodType:string}>;resolutionNote?:string};recrawlPlan?:{periods:Array<{type:string;year:number;value:number|null}>;note:string}};
type Report={items:Alert[];total:number;unread:number;page:number;pageSize:number;today?:{day:string;state:string};runs:Array<{day:string;state:string;details:{expected?:number;completed?:string[];reason?:string};updatedAt:string}>};
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const at=(v:string)=>new Date(v).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'});
const labels:Record<string,string>={waiting:'Chờ lượt cào 5h hoàn tất',running:'Đang đối chiếu',complete:'Đã kiểm tra',incomplete:'Chưa hoàn tất',paused:'Tạm dừng an toàn','not-checked':'Chưa kiểm tra'};
const value=(v:unknown):string=>v==null?'—':Array.isArray(v)?v.map(value).join(', '):typeof v==='object'?JSON.stringify(v):String(v);
const groups:Record<string,string>={total:'Tổng điểm',CKMB:'Công khai, minh bạch',TDGQ:'Tiến độ giải quyết',CLGQ:'Dịch vụ công trực tuyến',MDSH:'Số hóa hồ sơ',MDHL:'Mức độ hài lòng',TTTT:'Thanh toán trực tuyến'};
const fieldLabel=(c:Change,item:Detail)=>{const [identity,group]=c.field.split('/');return identity&&group&&item.details.provinceNames?.[identity]?`${item.details.provinceNames[identity]} · ${groups[group]??group}`:c.field;};
export function renderSourceMonitorReport(report:Report):string{
 return `<div class="source-monitor-summary"><strong>${report.unread} cảnh báo chưa đọc</strong><span>Đối chiếu kỳ tháng đã kết thúc · 06:00 · sau lượt cào 5h</span></div>
 ${report.today?.state==='not-started'?'<p>Chưa ghi nhận lượt kiểm tra hôm nay. Không kết luận nguồn không thay đổi.</p>':''}
 <h3>Lịch sử kiểm tra gần nhất</h3><div class="source-monitor-runs">${report.runs.length?report.runs.map(r=>`<div><strong>${esc(r.day.split('-').reverse().join('/'))}</strong><span>${esc(labels[r.state]??r.state)}</span><span>${r.details.completed?.length??0}/${r.details.expected??0} kỳ tháng</span>${r.details.reason?`<small>${esc(r.details.reason)}</small>`:''}</div>`).join(''):'<p>Chưa có lượt kiểm tra 6h. Không đồng nghĩa nguồn không thay đổi.</p>'}</div>
 <h3>Cảnh báo</h3><div class="source-monitor-list">${report.items.length?report.items.map(i=>`<article><div><strong>${esc(i.title)}</strong><p>${esc(at(i.updatedAt))} · ${i.resolved?'Đã xử lý':i.read?'Đã đọc':'Chưa đọc'} · ${i.changeCount} thay đổi</p></div><button type="button" data-source-alert="${esc(i.id)}">Xem chi tiết</button></article>`).join(''):'<p>Không có cảnh báo phù hợp bộ lọc.</p>'}</div>
 <nav class="source-monitor-pager" aria-label="Phân trang cảnh báo"><span>${report.total} cảnh báo · Trang ${report.page}/${Math.max(1,Math.ceil(report.total/report.pageSize))}</span><div><button type="button" data-source-page="${report.page-1}" ${report.page<=1?'disabled':''}>Trước</button><button type="button" data-source-page="${report.page+1}" ${report.page*report.pageSize>=report.total?'disabled':''}>Sau</button></div></nav>`;
}
export function renderSourceMonitorDetail(item:Detail):string{
 return `<header><h2 id="source-monitor-title">${esc(item.title)}</h2><button type="button" data-source-close>Đóng</button></header>
 <p>${esc(item.details.note??item.details.reason??'Kiểm tra nguồn; không tự cập nhật dữ liệu chính.')}</p>
 ${item.details.contexts?.length?`<details><summary>Phạm vi ghi nhận (${item.details.contexts.length})</summary><p>${item.details.contexts.map(c=>esc(`${c.rootName??c.rootId} · ${c.periodType==='year'?'Năm':c.periodType==='quarter'?'Quý':'Tháng'} ${c.value??''}${c.value?'/':''}${c.year}`)).join(' · ')}</p></details>`:''}
 ${item.details.changes?.length?`<div class="source-monitor-diff"><table><thead><tr><th>Nội dung</th><th>Đang lưu</th><th>Nguồn mới</th></tr></thead><tbody>${item.details.changes.map(c=>`<tr><th>${esc(fieldLabel(c,item))}</th><td>${esc(value(c.before))}</td><td>${esc(value(c.after))}</td></tr>`).join('')}</tbody></table></div>${item.changeCount>item.details.changes.length?`<p>Hiển thị ${item.details.changes.length}/${item.changeCount} thay đổi. Gói tin gốc được giữ để kiểm tra đầy đủ.</p>`:''}`:'<p>Lượt đối chiếu chưa thực hiện đủ; không kết luận dữ liệu không thay đổi.</p>'}
 ${item.recrawlPlan?`<details><summary>Phạm vi dự kiến cần cào lại — chưa thực hiện</summary><p>${esc(item.recrawlPlan.note)}</p><p>${item.recrawlPlan.periods.map(p=>esc(p.type==='month'?`Tháng ${p.value}/${p.year}`:p.type==='quarter'?`Quý ${p.value}/${p.year}`:`Năm ${p.year}`)).join(' · ')}</p></details>`:''}
 ${item.details.resolutionNote?`<p>Nội dung xử lý: ${esc(item.details.resolutionNote)}</p>`:''}
 <div class="actions"><button type="button" data-source-read ${item.read?'disabled':''}>Đánh dấu đã đọc</button></div>
 <form data-source-resolve><label>Nội dung xử lý<textarea name="note" maxlength="500" required rows="3"></textarea></label><button type="submit" ${item.resolved?'disabled':''}>Đánh dấu đã xử lý</button><p>Không công bố bản nháp, không tạo lệnh cào lại hoặc sửa công thức.</p></form><p data-source-dialog-message role="status"></p>`;
}
export function installSourceMonitor(root:HTMLElement,api:Api):void{
 const section=document.createElement('section');section.dataset.sourceMonitor='true';
 section.innerHTML='<h2>Cảnh báo nguồn dữ liệu</h2><div class="source-monitor-toolbar"><label>Trạng thái<select data-source-state><option value="open">Chưa xử lý</option><option value="unread">Chưa đọc</option><option value="resolved">Đã xử lý</option><option value="all">Tất cả</option></select></label><button type="button" data-source-refresh>Làm mới</button></div><p data-source-message role="status"></p><div data-source-body></div>';
 root.append(section);let page=1,read=0,opening=false;
 const message=section.querySelector<HTMLElement>('[data-source-message]')!,body=section.querySelector<HTMLElement>('[data-source-body]')!;
 const state=section.querySelector<HTMLSelectElement>('[data-source-state]')!;
 async function load(next=1){const revision=++read;message.textContent='Đang tải…';
  try{const report=await api<Report>(`admin/source-monitor?page=${next}&state=${state.value}`);if(revision!==read)return;
   page=report.page;body.innerHTML=renderSourceMonitorReport(report);message.textContent='';
   const button=root.querySelector('[data-admin-section="source-monitor"]');if(button)button.textContent=`Cảnh báo nguồn${report.unread?' ('+report.unread+')':''}`;
  }catch(error){if(revision===read)message.textContent=error instanceof Error?error.message:'Chưa tải được cảnh báo.';}
 }
 section.addEventListener('click',event=>{const button=(event.target as HTMLElement).closest<HTMLButtonElement>('button');if(!button||button.disabled)return;
  if(button.hasAttribute('data-source-refresh'))void load(page);
  if(button.dataset.sourcePage)void load(Number(button.dataset.sourcePage));
  if(button.dataset.sourceAlert)void open(button.dataset.sourceAlert);
 });
 state.addEventListener('change',()=>void load());
 root.addEventListener('click',event=>{if((event.target as HTMLElement).closest<HTMLElement>('[data-admin-section]')?.dataset.adminSection==='source-monitor')void load();});
 async function open(id:string){
  if(opening||root.querySelector('.source-monitor-dialog'))return;opening=true;
  try{const item=await api<Detail>('admin/source-monitor/'+id);const dialog=document.createElement('dialog');dialog.className='source-monitor-dialog';dialog.setAttribute('aria-labelledby','source-monitor-title');dialog.innerHTML=renderSourceMonitorDetail(item);root.append(dialog);
   dialog.querySelector('[data-source-close]')!.addEventListener('click',()=>dialog.close());dialog.addEventListener('close',()=>dialog.remove());
   const result=dialog.querySelector<HTMLElement>('[data-source-dialog-message]')!;
   let submitting=false;
   const review=async(action:'read'|'resolve',note='')=>{if(submitting)return;submitting=true;
    try{await api('admin/source-monitor/'+id+'/review',{action,note});dialog.close();await load(page);}catch(error){result.textContent=error instanceof Error?error.message:'Chưa xử lý được cảnh báo.';}finally{submitting=false;}};
   dialog.querySelector('[data-source-read]')!.addEventListener('click',()=>void review('read'));
   dialog.querySelector('form')!.addEventListener('submit',event=>{event.preventDefault();const note=dialog.querySelector<HTMLTextAreaElement>('textarea')!.value.trim();if(!note){result.textContent='Vui lòng ghi nội dung xử lý cảnh báo.';return;}void review('resolve',note);});
   dialog.showModal();
  }catch(error){message.textContent=error instanceof Error?error.message:'Chưa mở được cảnh báo.';}finally{opening=false;}
 }
 // One initial admin-only read for the badge; no new polling timer.
 void load();
}
