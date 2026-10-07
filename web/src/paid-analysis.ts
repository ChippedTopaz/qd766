interface Selection {rootDepartmentId:string;unitId:string;periodType:string;year:number;periodValue:number|null;scope:string;capturedAt:string;availableGroups?:string[];organization?:string;periodLabel?:string}
interface Card {id:string;groupId:string;kind:string;title:string;evidence:string;action:string;recommendation?:string}
interface Analysis {id:string;requestToken?:string;state:string;context?:{groupIds?:string[]};credits?:number;heldCredits?:number;queuePosition?:number|null;queueWaitMinutes?:number;createdAt:string;capturedAt:string;message:string;availableCredits?:number;reservedCredits?:number;result:{cards:Card[];limitations:string[]}|null}
interface Local {busy:boolean;confirming:boolean;error:string;token:string|null;analysis:Analysis|null;groupIds:string[]}
const groups=[['transparency','Công khai, minh bạch'],['dvc-progress-tree','Tiến độ giải quyết'],['provide-online-tree','Dịch vụ công trực tuyến'],['dossier-digitized','Số hóa hồ sơ'],['handling-satisfaction','Mức độ hài lòng'],['formality-online-payment-tree','Thanh toán trực tuyến']] as const;
const groupColors:Record<string,string>={'transparency':'#2563eb','dvc-progress-tree':'#059669','provide-online-tree':'#ec4899','dossier-digitized':'#8b5cf6','handling-satisfaction':'#d97706','formality-online-payment-tree':'#0891b2'};
const findingHeading=(card:Card)=>{const label=groups.find(([id])=>id===card.groupId)?.[1];const title=card.title.trim();return title&&title!==label&&title!==`Đánh giá ${label}`&&!/^Nhận định mẫu\s*[·–-]/.test(title)?`<h4>${esc(title)}</h4>`:'';};
const allowedGroups=(s:Selection)=>groups.filter(([id])=>!s.availableGroups||s.availableGroups.includes(id)).map(([id])=>String(id));
const cost=(ids:string[])=>ids.length*5;
const requestContext=(s:Selection)=>({rootDepartmentId:s.rootDepartmentId,unitId:s.unitId,periodType:s.periodType,year:s.year,periodValue:s.periodValue});
const memory=new Map<string,Local>();
let pollTimer:ReturnType<typeof setTimeout>|undefined;let pollVersion=0;
export function stopPaidAnalysisPolling():void {clearTimeout(pollTimer);pollTimer=undefined;pollVersion++;}
export function clearPaidAnalysis():void {stopPaidAnalysisPolling();memory.clear();}
const pending=(analysis:Analysis|null)=>analysis?.state==='queued'||analysis?.state==='running';
const esc=(value:string)=>value.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const key=(s:Selection)=>JSON.stringify([s.rootDepartmentId,s.unitId,s.periodType,s.year,s.periodValue]);
const entry=(s:Selection)=>{const k=key(s);if(!memory.has(k))memory.set(k,{busy:false,confirming:false,error:'',token:null,analysis:null,groupIds:allowedGroups(s)});return memory.get(k)!;};
export function renderPaidAnalysis(selection:Selection,authenticated:boolean,enabled=true):string {
  const local=entry(selection);const analysis=local.analysis;
  const renderCards=(id:string,section:'priority'|'actions')=>{
    const cards=analysis?.result?.cards.filter(c=>c.groupId===id&&(section==='actions'||c.kind==='priority'))??[];
    return cards.length?cards.map(c=>`<article class="analysis-card" data-analysis-finding="${esc(c.id)}">${findingHeading(c)}<p>${esc(section==='priority'?c.evidence:c.recommendation??c.action)}</p></article>`).join(''):section==='priority'?'<p class="analysis-empty">Không có phát hiện ưu tiên được ghi nhận cho nhóm này.</p>':'<p class="analysis-empty">Chưa có khuyến nghị được lưu cho nhóm này.</p>';
  };
  // Use the saved job's group selection, not the next run's checkbox draft.
  const resultGroups=groups.filter(([id])=>analysis?.context?.groupIds?.includes(id)||analysis?.result?.cards.some(card=>card.groupId===id));
  const resultPanels=analysis?.result?`<div class="analysis-results">${resultGroups.map(([id,label])=>`<section class="panel analysis-group-result" data-analysis-result-group="${id}" style="--analysis-group-color:${groupColors[id]}"><header class="analysis-group-heading"><h2>${label}</h2><button class="text-button" data-analysis-group="${id}">Xem chỉ tiêu →</button></header><div class="analysis-group-columns"><section><h3>Vấn đề cần ưu tiên</h3>${renderCards(id,'priority')}</section><section><h3>Hành động cần thực hiện</h3>${renderCards(id,'actions')}</section></div></section>`).join('')}</div>`:'';
  const stale=analysis?.state==='ready'&&Date.parse(selection.capturedAt)>Date.parse(analysis.capturedAt);
  const queueStatus=pending(analysis)?`<div class="credit-summary" role="status"><span>${analysis?.state==='queued'?`Đang chờ · Vị trí ${esc(String(analysis.queuePosition??'—'))}`:'Đang phân tích'}</span><strong>${analysis?.heldCredits??20} Credit đang giữ</strong>${analysis?.state==='queued'?'<button class="btn small" data-analysis-cancel-job>Hủy lượt chờ</button>':''}</div><p>Thời gian chờ tối đa ${esc(String(analysis?.queueWaitMinutes??10))} phút. Credit chưa ghi nhận thu.</p>`:'';
  const confirmation=local.confirming?`<div class="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="analysis-confirm-title"><div class="modal collection-confirm"><div class="modal-top"><strong id="analysis-confirm-title">Phân tích, đánh giá</strong><button class="btn small" data-analysis-cancel>Đóng</button></div><div class="brief"><h2>Chọn nhóm cần phân tích</h2><p>${esc(selection.organization??'Cơ quan đang chọn')} · ${esc(selection.periodLabel??`${selection.periodType} ${selection.year}`)}</p><fieldset class="analysis-group-picker"><legend>5 Credit / nhóm</legend>${groups.map(([id,label])=>`<label class="analysis-group-option"><input type="checkbox" data-analysis-select-group="${id}" ${local.groupIds.includes(id)?'checked':''} ${allowedGroups(selection).includes(id)?'':'disabled'}><span>${label}${allowedGroups(selection).includes(id)?'':'<small>Chưa đủ dữ liệu</small>'}</span><strong>5</strong></label>`).join('')}</fieldset><div class="analysis-actions"><button class="btn small" data-analysis-select-all>Chọn tất cả nhóm có dữ liệu</button><button class="btn small" data-analysis-select-none>Bỏ chọn</button></div><p>Đối chiếu tối đa ba kỳ liền trước cùng loại và các cơ quan cùng cấp có số hồ sơ trong khoảng ±20%.</p><div class="credit-summary"><span>${local.groupIds.length} nhóm đã chọn</span><strong>${cost(local.groupIds)} Credit</strong></div><p>Chỉ ghi nhận thu khi lưu thành công toàn bộ kết quả. Hoàn toàn bộ Credit đã giữ nếu lượt phân tích thất bại.</p><div class="analysis-actions"><button class="btn" data-analysis-cancel>Hủy</button><button class="btn primary" data-analysis-confirm ${local.groupIds.length?'':'disabled'}>Phân tích · ${cost(local.groupIds)} Credit</button></div></div></div></div>`:'';
  return `${confirmation}<section class="panel paid-analysis"><div class="panel-head"><div><h2>Phân tích - đánh giá <span class="analysis-experimental">(Đang thử nghiệm)</span></h2></div><div class="analysis-actions"><button class="btn" data-analysis-read ${local.busy||!authenticated?'disabled':''}>Xem kết quả đã lưu</button><button class="btn primary" data-analysis-start ${local.busy||pending(analysis)||!enabled||!authenticated||selection.scope!=='all'?'disabled':''}>${local.busy?'Đang gửi…':pending(analysis)?'Đang chờ / xử lý':local.token?'Tiếp tục lượt phân tích':'Phân tích điểm số'}</button></div></div><div class="panel-body" aria-live="polite">${!enabled?'<p>Phân tích Gemini chưa được kích hoạt.</p>':''}${selection.scope!=='all'?'<p>Phân tích hiện áp dụng cho tất cả TTHC của cơ quan trong kỳ đang chọn.</p>':''}${local.busy?'<p role="status">Đang xử lý yêu cầu. Anh/chị có thể tiếp tục sử dụng các mục khác.</p>':''}${local.error?`<p class="negative">${esc(local.error)}</p>`:''}${queueStatus}${analysis?`<p>Phân tích lúc ${esc(new Date(analysis.createdAt).toLocaleString('vi-VN'))} · Dữ liệu ${esc(new Date(analysis.capturedAt).toLocaleString('vi-VN'))}</p>`:''}${stale?'<p>Kết quả đã lưu sử dụng dữ liệu trước lần cập nhật hiện tại.</p>':''}</div></section>${resultPanels}${analysis?.result?`<details class="comparison-notes"><summary>Lưu ý</summary>${analysis.result.limitations.map(text=>`<p>${esc(text)}</p>`).join('')}</details>`:''}`;
}
export function bindPaidAnalysis(selection:Selection,csrf:string,onChange:()=>void,onGroup:(id:string)=>void,onWallet:(available:number,reserved:number)=>void):void {
  const local=entry(selection);
  const update=(value:Analysis)=>{local.analysis=value;local.token=pending(value)?value.requestToken??local.token:null;if(pending(value)&&value.context?.groupIds)local.groupIds=[...value.context.groupIds];local.error=pending(value)||value.state==='ready'?'':value.message;if(value.availableCredits!==undefined)onWallet(value.availableCredits,value.reservedCredits??0);};
  const run=async()=>{
    if(local.busy||selection.scope!=='all'||!local.groupIds.length)return;
    local.confirming=false;
    local.busy=true;local.error='';local.token??=crypto.randomUUID();onChange();
    try{
      const response=await fetch('/api/v1/me/analysis',{method:'POST',headers:{'Content-Type':'application/json','X-QD766-CSRF':csrf},body:JSON.stringify({...requestContext(selection),groupIds:local.groupIds,token:local.token,expectedCredits:cost(local.groupIds)})});
      const value=await response.json();
      if(!response.ok){if(response.status<500)local.token=null;throw new Error(typeof value.detail==='string'?value.detail:'Không thực hiện được phân tích.');}
      update(value as Analysis);
    }catch(error){local.error=error instanceof Error?error.message:'Chưa xác nhận được kết quả. Xem kết quả đã lưu trước khi gửi lại.';}
    finally{local.busy=false;onChange();}
  };
  document.querySelector('[data-analysis-start]')?.addEventListener('click',()=>{
    if(local.busy||local.confirming||pending(local.analysis)||selection.scope!=='all')return;
    return(async()=>{
      local.busy=true;local.error='';onChange();
      try{
        const response=await fetch('/api/v1/me/analysis/availability',{cache:'no-store'}),value=await response.json();
        if(!response.ok)throw new Error(value.detail??'Không kiểm tra được trạng thái phân tích.');
        if(!value.available)throw new Error('Tính năng tạm thời không khả dụng do đang trong quá trình nâng cấp.');
        local.busy=false;
        if(local.token){await run();return;}
        local.groupIds=local.groupIds.filter(id=>allowedGroups(selection).includes(id));
        local.confirming=true;
      }catch(error){local.error=error instanceof Error?error.message:'Không kiểm tra được trạng thái phân tích.';}
      finally{local.busy=false;onChange();document.querySelector<HTMLButtonElement>('[data-analysis-cancel]')?.focus();}
    })();
  });
  document.querySelector('[data-analysis-confirm]')?.addEventListener('click',()=>{if(local.confirming)void run();});
  document.querySelectorAll<HTMLInputElement>('[data-analysis-select-group]').forEach(input=>input.addEventListener('change',()=>{
    if(local.busy||local.token||!local.confirming)return;
    const id=input.dataset.analysisSelectGroup!;
    if(!allowedGroups(selection).includes(id))return;
    local.groupIds=input.checked?[...new Set([...local.groupIds,id])]:local.groupIds.filter(key=>key!==id);
    onChange();document.querySelector<HTMLInputElement>(`[data-analysis-select-group="${id}"]`)?.focus();
  }));
  document.querySelector('[data-analysis-select-all]')?.addEventListener('click',()=>{if(local.confirming&&!local.busy&&!local.token){local.groupIds=allowedGroups(selection);onChange();}});
  document.querySelector('[data-analysis-select-none]')?.addEventListener('click',()=>{if(local.confirming&&!local.busy&&!local.token){local.groupIds=[];onChange();}});
  const cancel=()=>{local.confirming=false;onChange();document.querySelector<HTMLButtonElement>('[data-analysis-start]')?.focus();};
  document.querySelectorAll<HTMLElement>('[data-analysis-cancel]').forEach(button=>button.addEventListener('click',cancel));
  document.querySelector<HTMLElement>('[aria-labelledby="analysis-confirm-title"]')?.addEventListener('keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();cancel();return;}
    if(event.key==='Tab'){
      const buttons=Array.from(document.querySelectorAll<HTMLElement>('[aria-labelledby="analysis-confirm-title"] button:not([disabled]),[aria-labelledby="analysis-confirm-title"] input:not([disabled])'));
      const first=buttons[0],last=buttons[buttons.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
    }
  });
  document.querySelector('[data-analysis-read]')?.addEventListener('click',async()=>{
    if(local.busy)return;local.busy=true;local.error='';onChange();
    try{
      const query=new URLSearchParams({root_department_id:selection.rootDepartmentId,unit_id:selection.unitId,period_type:selection.periodType,year:String(selection.year)});
      if(selection.periodValue!==null)query.set('period_value',String(selection.periodValue));
      const response=await fetch('/api/v1/me/analysis/latest?'+query,{cache:'no-store'});const body=await response.json();
      if(!response.ok)throw new Error(body.detail??'Không tải được kết quả.');
      if(body.analysis)update(body.analysis);else local.error='Chưa có kết quả phân tích đã lưu cho lựa chọn này.';
    }catch(error){local.error=error instanceof Error?error.message:'Không tải được kết quả.';}
    finally{local.busy=false;onChange();}
  });
  document.querySelectorAll<HTMLElement>('[data-analysis-group]').forEach(button=>button.addEventListener('click',()=>onGroup(button.dataset.analysisGroup!)));
  document.querySelector('[data-analysis-cancel-job]')?.addEventListener('click',async()=>{
    if(local.busy||local.analysis?.state!=='queued'||!local.token)return;
    local.busy=true;local.error='';onChange();
    try{
      const groupIds=local.analysis.context?.groupIds;
      const response=await fetch('/api/v1/me/analysis/cancel',{method:'POST',headers:{'Content-Type':'application/json','X-QD766-CSRF':csrf},body:JSON.stringify({...requestContext(selection),...(groupIds?{groupIds}:{}),token:local.token,expectedCredits:local.analysis.heldCredits??20})});
      const value=await response.json();if(!response.ok)throw new Error(value.detail??'Không hủy được lượt chờ.');
      update(value as Analysis);
    }catch(error){local.error=error instanceof Error?error.message:'Không hủy được lượt chờ.';}
    finally{local.busy=false;onChange();}
  });
  stopPaidAnalysisPolling();
  if(pending(local.analysis)&&!local.busy){
    const version=pollVersion;const id=local.analysis!.id;
    const poll=async()=>{
      if(version!==pollVersion)return;
      if(document.visibilityState==='hidden'){pollTimer=setTimeout(poll,5000);return;}
      try{
        const response=await fetch('/api/v1/me/analysis/'+encodeURIComponent(id)+'/status',{cache:'no-store'});
        const value=await response.json();if(version!==pollVersion)return;
        if(!response.ok)throw new Error(value.detail??'Chưa đọc được trạng thái phân tích.');
        update(value as Analysis);
      }catch(error){if(version!==pollVersion)return;local.error=error instanceof Error?error.message:'Chưa đọc được trạng thái.';}
      onChange();
    };
    pollTimer=setTimeout(poll,5000);
  }
}
