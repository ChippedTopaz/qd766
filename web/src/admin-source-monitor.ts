type Api=<T>(path:string,body?:unknown)=>Promise<T>;
type Subject={groupName:string;indicatorName:string;parameterName:string};
type Alert={id:string;title:string;kind:string;createdAt:string;updatedAt:string;read:boolean;resolved:boolean;occurrences:number;changeCount:number;confirmed:boolean;groups?:string[];subjects?:Subject[];subjectCount?:number;affectedProvinceCount?:number};
type Change={field:string;before:unknown;after:unknown;change:string;display?:Subject&{parameterCode?:string;metricCode?:string|null;scopeLabel?:string|null;entityName?:string|null;sourcePath?:string}};
type Detail=Alert&{details:{changes?:Change[];note?:string;reason?:string;confirmed?:boolean;provinceNames?:Record<string,string>;contexts?:Array<{rootId:string;rootName?:string;group:string;year:number;value:number|null;periodType:string}>;resolutionNote?:string};recrawlPlan?:{periods:Array<{type:string;year:number;value:number|null}>;note:string}};
import {logRange,publishLogBadge,compactLogFilters,installLogFilterPopover} from './admin-log-ui.js';
type Report={grouped?:false;items:Alert[];total:number;unread:number;openCount?:number;kinds?:string[];page:number;pageSize:number;today?:{day:string;state:string};runs:Array<{day:string;state:string;details:{expected?:number;completed?:string[];reason?:string};updatedAt:string}>};
type Batch={id:string;title:string;label:string;day:string|null;updatedAt:string;contentCount:number;changeCount:number;unreadCount:number;openCount:number;kinds:Record<string,number>};
type BatchReport=Omit<Report,'items'|'grouped'>&{grouped:true;items:Batch[]};
type BatchDetail=Batch&{items:Alert[];page:number;pageSize:number};
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const at=(v:string)=>new Date(v).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'});
const labels:Record<string,string>={waiting:'Chờ lượt cào 5h hoàn tất',running:'Đang đối chiếu',complete:'Đã kiểm tra',incomplete:'Chưa hoàn tất',paused:'Tạm dừng an toàn','not-checked':'Chưa kiểm tra'};
const value=(v:unknown):string=>v==null?'—':typeof v==='boolean'?v?'Có':'Không':Array.isArray(v)?v.map(value).join(', '):typeof v==='object'?JSON.stringify(v):String(v);
const groups:Record<string,string>={total:'Tổng điểm',CKMB:'Công khai, minh bạch',TDGQ:'Tiến độ giải quyết',CLGQ:'Dịch vụ công trực tuyến',MDSH:'Số hóa hồ sơ',MDHL:'Mức độ hài lòng',TTTT:'Thanh toán trực tuyến'};
const parameterNames:Record<string,string>={totalMaxScore:'Điểm tối đa của nhóm',maxScore:'Điểm tối đa của chỉ tiêu',threshold:'Ngưỡng đạt điểm (%)',targetRatio:'Tỷ lệ mục tiêu (%)',formula:'Công thức tính',formulaVersion:'Phiên bản công thức',scorePolicy:'Quy tắc chấm điểm',weight:'Trọng số',name:'Tên chỉ tiêu',groupCodes:'Danh sách nhóm chỉ tiêu'};
export function sourceChangeLabel(c:Change,item:Detail):NonNullable<Change['display']>{
 if(c.display)return c.display;
 const [identity,key]=c.field.split('/'),province=identity?item.details.provinceNames?.[identity]:null;
 if(province&&key)return {groupName:groups[key]??`Nhóm mới: ${key}`,indicatorName:key==='total'?'Tổng điểm':'Điểm nhóm chỉ tiêu',parameterName:'Điểm ghi nhận',parameterCode:'score',scopeLabel:'Cấp tỉnh',entityName:province,sourcePath:c.field};
 const parameter=c.field.split(':').at(-1)??c.field;
 return {groupName:'Chưa xác định nhóm từ bằng chứng đã lưu',indicatorName:'Chưa có tên chỉ tiêu trong bằng chứng đã lưu',parameterName:parameterNames[parameter]??'Tham số mới / chưa có tên diễn giải',sourcePath:c.field};
}
function changeValue(c:Change,v:unknown):string{
 if(c.display?.parameterCode==='groupCodes')return Array.isArray(v)?v.map(x=>changeValue(c,x)).join(' · '):v==null?'—':groups[String(v)]??`Nhóm chưa có tên (${value(v)})`;
 return value(v);
}
const kindNames:Record<string,string>={structure:'Cơ cấu điểm / chỉ tiêu','closed-period':'Dữ liệu kỳ đã kết thúc','check-failed':'Lỗi đối chiếu'};
const batchDay=(b:Batch)=>b.day?esc(b.day.split('-').reverse().join('/')):'';
const batchKinds=(b:Batch)=>Object.entries(b.kinds).filter(([,n])=>n).map(([k,n])=>`${esc(kindNames[k]??k)}: <b>${n}</b> nội dung`).join(' · ');
export function renderSourceMonitorBatches(report:BatchReport):string{
 return `<div class="source-monitor-summary"><strong>${report.unread} đợt cảnh báo chưa đọc</strong><span>Mỗi đợt một thông báo · xử lý riêng từng nội dung</span></div>
 ${report.today?.state==='not-started'?'<p>Chưa ghi nhận lượt kiểm tra hôm nay. Không kết luận nguồn không thay đổi.</p>':''}
 <div class="source-monitor-list">${report.items.map(b=>`<article><div><strong>${esc(b.title)}${b.day?' · '+batchDay(b):''}</strong><p>${esc(b.label)} · ${b.changeCount} thay đổi · ${b.contentCount} nội dung</p><p>${batchKinds(b)}</p><p>${b.openCount?`${b.openCount} chưa xử lý`:'Đã xử lý toàn bộ'} · ${b.unreadCount?`${b.unreadCount} chưa đọc`:'Đã đọc toàn bộ'}</p></div><button type="button" data-source-batch="${esc(b.id)}">Xem chi tiết</button></article>`).join('')||'<p>Không có cảnh báo phù hợp bộ lọc.</p>'}</div>
 <nav class="source-monitor-pager" aria-label="Phân trang đợt cảnh báo"><span>${report.total} đợt · Trang ${report.page}/${Math.max(1,Math.ceil(report.total/report.pageSize))}</span><div><button type="button" data-source-page="${report.page-1}" ${report.page<=1?'disabled':''}>Trước</button><button type="button" data-source-page="${report.page+1}" ${report.page*report.pageSize>=report.total?'disabled':''}>Sau</button></div></nav>`;
}
export function renderSourceMonitorBatch(b:BatchDetail):string{
 return `<header><h2 id="source-batch-title">${esc(b.title)}${b.day?' · '+batchDay(b):''}</h2><button type="button" data-batch-close>Đóng</button></header><p>${esc(b.label)} · ${b.changeCount} thay đổi · ${b.contentCount} nội dung</p><p>${batchKinds(b)}</p>
 <div class="source-monitor-list">${Object.keys(kindNames).map(kind=>{const items=b.items.filter(i=>i.kind===kind);return items.length?`<h3>${esc(kindNames[kind])}</h3>${items.map(i=>`<article><div><strong>${esc(i.title)}</strong>${i.groups?.length?`<p class="source-alert-groups">Nhóm chỉ tiêu: <b>${i.groups.map(esc).join(' · ')}</b></p>`:''}<div class="source-alert-subjects">${(i.subjects??[]).slice(0,2).map(s=>`<p>${esc(s.indicatorName)} — ${esc(s.parameterName)}</p>`).join('')}</div><p>${i.changeCount} thay đổi · ${i.resolved?'Đã xử lý':i.read?'Đã đọc':'Chưa đọc'}${i.occurrences>1?' · '+i.occurrences+' lần ghi nhận (đã gộp)':''}</p></div><button type="button" data-source-alert="${esc(i.id)}">Xem / xử lý</button></article>`).join('')}`:'';}).join('')}</div>
 <nav class="source-monitor-pager" aria-label="Phân trang nội dung cảnh báo"><span>${b.contentCount} nội dung · Trang ${b.page}/${Math.max(1,Math.ceil(b.contentCount/b.pageSize))}</span><div><button type="button" data-batch-page="${b.page-1}" ${b.page<=1?'disabled':''}>Trước</button><button type="button" data-batch-page="${b.page+1}" ${b.page*b.pageSize>=b.contentCount?'disabled':''}>Sau</button></div></nav><div class="actions"><button type="button" data-batch-read ${b.unreadCount?'':'disabled'}>Đánh dấu cả đợt đã đọc</button></div><p data-batch-message role="status"></p>`;
}
export function renderSourceMonitorReport(report:Report|BatchReport):string{
 if(report.grouped)return renderSourceMonitorBatches(report);
 return `<div class="source-monitor-summary"><strong>${report.unread} cảnh báo chưa đọc</strong><span>Đối chiếu kỳ tháng đã kết thúc · 06:00 · sau lượt cào 5h</span></div>
 ${report.today?.state==='not-started'?'<p>Chưa ghi nhận lượt kiểm tra hôm nay. Không kết luận nguồn không thay đổi.</p>':''}
 ${!report.runs.length?'<p>Chưa có lượt kiểm tra 6h. Không đồng nghĩa nguồn không thay đổi.</p>':''}
 <h3>Cảnh báo</h3><div class="source-monitor-list">${report.items.length?report.items.map(i=>`<article><div><strong>${esc(i.title)}</strong>${i.groups?.length?`<p class="source-alert-groups">Nhóm chỉ tiêu: <b>${i.groups.map(esc).join(' · ')}</b></p>`:''}${i.subjects?.length?`<div class="source-alert-subjects">${i.subjects.slice(0,2).map(s=>`<p>${esc(s.indicatorName)} — <span>${esc(s.parameterName)}</span></p>`).join('')}${(i.subjectCount??0)>2?`<small>Và ${(i.subjectCount??0)-2} nội dung khác trong chi tiết.</small>`:''}</div>`:''}<p>${esc(at(i.updatedAt))} · ${i.resolved?'Đã xử lý':i.read?'Đã đọc':'Chưa đọc'} · ${i.changeCount} thay đổi</p></div><button type="button" data-source-alert="${esc(i.id)}">Xem chi tiết</button></article>`).join(''):'<p>Không có cảnh báo phù hợp bộ lọc.</p>'}</div>
 <nav class="source-monitor-pager" aria-label="Phân trang cảnh báo"><span>${report.total} cảnh báo · Trang ${report.page}/${Math.max(1,Math.ceil(report.total/report.pageSize))}</span><div><button type="button" data-source-page="${report.page-1}" ${report.page<=1?'disabled':''}>Trước</button><button type="button" data-source-page="${report.page+1}" ${report.page*report.pageSize>=report.total?'disabled':''}>Sau</button></div></nav>`;
}
export function renderSourceMonitorDetail(item:Detail):string{
 return `<header><h2 id="source-monitor-title">${esc(item.title)}</h2><button type="button" data-source-close>Đóng</button></header>
 <p>${esc(item.details.note??item.details.reason??'Kiểm tra nguồn; không tự cập nhật dữ liệu chính.')}</p>
 ${item.affectedProvinceCount?`<p>Phạm vi ghi nhận: <strong>${item.affectedProvinceCount} tỉnh/thành phố</strong>${item.occurrences>1?` · ${item.occurrences} lần ghi nhận đã gộp`:''}.</p>`:''}
 ${item.details.contexts?.length?`<details><summary>Phạm vi ghi nhận (${item.details.contexts.length})</summary><p>${item.details.contexts.map(c=>esc(`${c.rootName??c.rootId} · ${c.periodType==='year'?'Năm':c.periodType==='quarter'?'Quý':'Tháng'} ${c.value??''}${c.value?'/':''}${c.year}`)).join(' · ')}</p></details>`:''}
 ${item.details.changes?.length?`<div class="source-monitor-diff"><table class="source-change-table"><thead><tr><th>Nhóm chỉ tiêu</th><th>Chỉ tiêu / tham số thay đổi</th><th>Đang lưu</th><th>Nguồn mới</th></tr></thead><tbody>${item.details.changes.map(c=>{const d=sourceChangeLabel(c,item);return `<tr><th>${esc(d.groupName)}${d.entityName?`<small>${esc(d.entityName)}</small>`:''}${d.scopeLabel?`<small>${esc(d.scopeLabel)}</small>`:''}</th><td><strong>${esc(d.indicatorName)}</strong><span class="source-change-parameter">${esc(d.parameterName)}</span><small>${c.change==='added'?'Bổ sung':c.change==='removed'?'Loại bỏ':'Điều chỉnh'}</small><details class="source-change-code"><summary>Mã nguồn${d.metricCode?' · '+esc(d.metricCode):''}</summary><code>${esc(c.field)}</code></details></td><td>${esc(changeValue(c,c.before))}</td><td>${esc(changeValue(c,c.after))}</td></tr>`;}).join('')}</tbody></table></div>${item.changeCount>item.details.changes.length?`<p>Hiển thị ${item.details.changes.length}/${item.changeCount} thay đổi. Gói tin gốc được giữ để kiểm tra đầy đủ.</p>`:''}`:'<p>Lượt đối chiếu chưa thực hiện đủ; không kết luận dữ liệu không thay đổi.</p>'}
 ${item.recrawlPlan?`<details><summary>Phạm vi dự kiến cần cào lại — chưa thực hiện</summary><p>${esc(item.recrawlPlan.note)}</p><p>${item.recrawlPlan.periods.map(p=>esc(p.type==='month'?`Tháng ${p.value}/${p.year}`:p.type==='quarter'?`Quý ${p.value}/${p.year}`:`Năm ${p.year}`)).join(' · ')}</p></details>`:''}
 ${item.details.resolutionNote?`<p>Nội dung xử lý: ${esc(item.details.resolutionNote)}</p>`:''}
 <div class="actions"><button type="button" data-source-read ${item.read?'disabled':''}>Đánh dấu đã đọc</button></div>
 <form data-source-resolve><label>Nội dung xử lý<textarea name="note" maxlength="500" required rows="3"></textarea></label><button type="submit" ${item.resolved?'disabled':''}>Đánh dấu đã xử lý</button><p>Không công bố bản nháp, không tạo lệnh cào lại hoặc sửa công thức.</p></form><p data-source-dialog-message role="status"></p>`;
}
export function installSourceMonitor(root:HTMLElement,api:Api):void{
 const section=document.createElement('section');section.dataset.sourceMonitor='true';section.dataset.logView='source';section.hidden=true;
 section.innerHTML=`<div class="log-title-row"><h2>Cảnh báo nguồn</h2><button type="button" data-source-refresh>Làm mới</button></div>${compactLogFilters('<label class="log-field-state">Trạng thái<select data-source-state><option value="open">Chưa xử lý</option><option value="unread">Chưa đọc</option><option value="resolved">Đã xử lý</option><option value="all">Tất cả</option></select></label><label class="log-field-kind">Loại cảnh báo<select data-source-kind><option value="">Tất cả</option><option value="structure">Cơ cấu điểm / chỉ tiêu</option><option value="closed-period">Dữ liệu kỳ đã kết thúc</option><option value="check-failed">Lỗi đối chiếu</option></select></label>')}<p data-source-message role="status"></p><div data-source-body></div>`;
 root.append(section);let page=1,read=0,opening=false,refreshBatch:(()=>Promise<void>)|undefined;
 installLogFilterPopover(section,()=>void load());
 const message=section.querySelector<HTMLElement>('[data-source-message]')!,body=section.querySelector<HTMLElement>('[data-source-body]')!;
 const state=section.querySelector<HTMLSelectElement>('[data-source-state]')!;
 async function load(next=1){const revision=++read;message.textContent='Đang tải…';
  try{const params=new URLSearchParams({page:String(next),state:state.value,grouped:'true'});logRange(section,params);const kind=section.querySelector<HTMLSelectElement>('[data-source-kind]')!.value;if(kind)params.set('kind',kind);const report=await api<Report|BatchReport>(`admin/source-monitor?${params}`);if(revision!==read)return;
   page=report.page;body.innerHTML=renderSourceMonitorReport(report);message.textContent='';
   publishLogBadge(root,report.openCount??report.unread);
  }catch(error){if(revision===read){body.innerHTML='';message.textContent=error instanceof Error?error.message:'Chưa tải được cảnh báo.';}}
 }
 section.addEventListener('click',event=>{const button=(event.target as HTMLElement).closest<HTMLButtonElement>('button');if(!button||button.disabled)return;
  if(button.hasAttribute('data-source-refresh'))void load(page);
  if(button.dataset.sourcePage)void load(Number(button.dataset.sourcePage));
  if(button.dataset.sourceAlert)void open(button.dataset.sourceAlert);
  if(button.dataset.sourceBatch)void openBatch(button.dataset.sourceBatch);
 });
 section.addEventListener('change',()=>void load());
 root.addEventListener('qd766-log-view',event=>{if((event as CustomEvent<string>).detail==='source')void load(page);else ++read;});
 async function openBatch(id:string){
  if(opening||root.querySelector('.source-monitor-batch-dialog'))return;opening=true;
  const dialog=document.createElement('dialog');dialog.className='source-monitor-batch-dialog admin-log-dialog';dialog.setAttribute('aria-labelledby','source-batch-title');
  let current=1,busy=false;
  const reload=async(next=current)=>{const b=await api<BatchDetail>('admin/source-monitor/batches/detail?'+new URLSearchParams({batchId:id,page:String(next)}));current=b.page;dialog.innerHTML=renderSourceMonitorBatch(b);};
  try{await reload();root.append(dialog);refreshBatch=()=>reload();dialog.addEventListener('close',()=>{refreshBatch=undefined;dialog.remove();});
   dialog.addEventListener('click',event=>{const button=(event.target as HTMLElement).closest<HTMLButtonElement>('button');if(!button||button.disabled)return;
    if(button.hasAttribute('data-batch-close'))dialog.close();
    if(button.dataset.sourceAlert)void open(button.dataset.sourceAlert);
    const action=async()=>{if(busy)return;busy=true;try{
     if(button.hasAttribute('data-batch-read')){await api('admin/source-monitor/batches/read',{batchId:id});await load(page);await reload();}
     else if(button.dataset.batchPage)await reload(Number(button.dataset.batchPage));
    }catch(error){dialog.querySelector<HTMLElement>('[data-batch-message]')!.textContent=error instanceof Error?error.message:'Chưa tải được đợt cảnh báo.';}finally{busy=false;}};
    if(button.hasAttribute('data-batch-read')||button.dataset.batchPage)void action();
   });dialog.showModal();
  }catch(error){dialog.remove();message.textContent=error instanceof Error?error.message:'Chưa mở được đợt cảnh báo.';}finally{opening=false;}
 }
 async function open(id:string){
  if(opening||root.querySelector('.source-monitor-dialog'))return;opening=true;
  try{const item=await api<Detail>('admin/source-monitor/'+id);const dialog=document.createElement('dialog');dialog.className='source-monitor-dialog admin-log-dialog';dialog.setAttribute('aria-labelledby','source-monitor-title');dialog.innerHTML=renderSourceMonitorDetail(item);root.append(dialog);
   dialog.querySelector('[data-source-close]')!.addEventListener('click',()=>dialog.close());dialog.addEventListener('close',()=>dialog.remove());
   const result=dialog.querySelector<HTMLElement>('[data-source-dialog-message]')!;
   let submitting=false;
   const review=async(action:'read'|'resolve',note='')=>{if(submitting)return;submitting=true;
    try{await api('admin/source-monitor/'+id+'/review',{action,note});dialog.close();await load(page);await refreshBatch?.();}catch(error){result.textContent=error instanceof Error?error.message:'Chưa xử lý được cảnh báo.';}finally{submitting=false;}};
   dialog.querySelector('[data-source-read]')!.addEventListener('click',()=>void review('read'));
   dialog.querySelector('form')!.addEventListener('submit',event=>{event.preventDefault();const note=dialog.querySelector<HTMLTextAreaElement>('textarea')!.value.trim();if(!note){result.textContent='Vui lòng ghi nội dung xử lý cảnh báo.';return;}void review('resolve',note);});
   dialog.showModal();
  }catch(error){message.textContent=error instanceof Error?error.message:'Chưa mở được cảnh báo.';}finally{opening=false;}
 }
 // Lazy read: opening another admin menu must not load alerts or start a timer.
}
