type Api=<T>(path:string,body?:unknown)=>Promise<T>;
type Pending={id:string;name:string;email:string;province:string;unit:string;provinceId:string;unitId:string};
type Link={id:string;expiresAt:string;registeredCount:number;maxRegistrations:number;revoked:boolean};
type Directory={provinces:Array<{id:string;name:string}>;units:Array<{id:string;name:string}>};
const esc=(value:unknown)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));

export async function installRegistrationAdmin(root:HTMLElement,api:Api,onReview:()=>Promise<void>):Promise<void>{
  const policy=await api<{sharedRegistrationEnabled?:boolean}>('access-policy');
  if(!policy.sharedRegistrationEnabled)return;
  const links=document.createElement('section');links.dataset.sharedLinks='true';
  links.innerHTML='<h2>Link đăng ký dùng chung</h2><p>Người dùng tự chọn tỉnh và cơ quan. Chỉ cấp quyền cơ quan sau khi duyệt.</p><form data-create-link><div class="form-grid"><label>Hạn link (ngày)<input name="days" type="number" min="1" max="30" value="7" required></label><label>Số người đăng ký tối đa<input name="max" type="number" min="1" max="1000" value="100" required></label></div><div class="actions"><button type="submit" class="primary">Tạo link dùng chung</button></div></form><div data-link-result></div><p data-link-message role="status"></p><div class="scroll"><table><thead><tr><th>Hết hạn</th><th>Đã đăng ký</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody data-links></tbody></table></div>';
  const pending=document.createElement('section');pending.dataset.registrationReview='true';
  pending.innerHTML='<h2>Đăng ký chờ duyệt</h2><p>Chỉ cấp quyền xem cơ quan được chọn. Khi duyệt, tự cấp 1 tháng dùng thử và 100 Credit một lần.</p><div class="actions"><button data-refresh> Làm mới</button><button class="primary" data-review="approve">Duyệt đã chọn</button><button data-review="reject">Từ chối đã chọn</button></div><p data-review-message role="status"></p><div class="scroll"><table><thead><tr><th><input type="checkbox" data-all aria-label="Chọn tối đa 100 yêu cầu"></th><th>Người đăng ký</th><th>Tỉnh/thành phố</th><th>Cơ quan, đơn vị</th><th>Thao tác</th></tr></thead><tbody data-pending></tbody></table></div><form data-edit hidden><h3>Điều chỉnh cơ quan</h3><div class="form-grid"><label>Tỉnh/thành phố<select data-edit-province required></select></label><label>Cơ quan<select data-edit-unit required></select></label></div><div class="actions"><button type="submit">Lưu lựa chọn</button><button type="button" data-cancel-edit>Hủy</button></div></form>';
  root.append(links,pending);
  let rows:Pending[]=[],editing:string|null=null;
  const message=(scope:HTMLElement,selector:string,text:string)=>{scope.querySelector(selector)!.textContent=text;};
  const loadLinks=async()=>{
    const items=await api<Link[]>('admin/registration-links');
    links.querySelector('[data-links]')!.innerHTML=items.map(item=>`<tr><td>${esc(new Date(item.expiresAt).toLocaleString('vi-VN'))}</td><td>${item.registeredCount}/${item.maxRegistrations}</td><td>${item.revoked?'Đã thu hồi':new Date(item.expiresAt).getTime()<Date.now()?'Hết hạn':item.registeredCount>=item.maxRegistrations?'Đủ số người':'Đang mở'}</td><td>${item.revoked?'':`<button data-revoke-link="${esc(item.id)}">Thu hồi</button>`}</td></tr>`).join('');
  };
  const loadPending=async()=>{
    rows=await api<Pending[]>('admin/registrations');
    pending.querySelector('[data-pending]')!.innerHTML=rows.length?rows.map(item=>`<tr><td><input type="checkbox" data-registration-id="${esc(item.id)}" aria-label="Chọn ${esc(item.name)}"></td><td>${esc(item.name)}<br><small>${esc(item.email)}</small></td><td>${esc(item.province)}</td><td>${esc(item.unit)}</td><td><button data-edit-registration="${esc(item.id)}">Điều chỉnh</button></td></tr>`).join(''):'<tr><td colspan="5">Không có đăng ký chờ duyệt.</td></tr>';
    pending.querySelector<HTMLInputElement>('[data-all]')!.checked=false;
  };
  async function action(scope:HTMLElement,selector:string,work:()=>Promise<void>){try{await work();}catch(error){message(scope,selector,error instanceof Error?error.message:'Không thực hiện được yêu cầu.');}}
  links.querySelector('form')!.addEventListener('submit',event=>{
    event.preventDefault();const form=event.currentTarget as HTMLFormElement;const button=form.querySelector<HTMLButtonElement>('button')!;button.disabled=true;
    void action(links,'[data-link-message]',async()=>{try{
      const values=new FormData(form);const item=await api<{token:string}>('admin/registration-links',{days:Number(values.get('days')),maxRegistrations:Number(values.get('max'))});
      const url=`${location.origin}/#register=${item.token}`;
      const result=links.querySelector('[data-link-result]')!;result.replaceChildren();
      const link=document.createElement('a');link.href=url;link.textContent=url;link.style.overflowWrap='anywhere';
      const copy=document.createElement('button');copy.type='button';copy.textContent='Sao chép link';
      copy.addEventListener('click',()=>void action(links,'[data-link-message]',async()=>{await navigator.clipboard.writeText(url);message(links,'[data-link-message]','Đã sao chép link dùng chung.');}));
      result.append(link,copy);message(links,'[data-link-message]','Link chỉ hiển thị lần này. Có thể gửi cùng link cho nhiều người.');await loadLinks();
    }finally{button.disabled=false;}});
  });
  links.addEventListener('click',event=>{const button=(event.target as HTMLElement).closest<HTMLButtonElement>('[data-revoke-link]');if(button)void action(links,'[data-link-message]',async()=>{await api(`admin/registration-links/${button.dataset.revokeLink}/revoke`,{});await loadLinks();message(links,'[data-link-message]','Đã thu hồi link; không nhận đăng ký mới.');});});
  pending.querySelector('[data-refresh]')!.addEventListener('click',()=>void action(pending,'[data-review-message]',loadPending));
  pending.querySelector<HTMLInputElement>('[data-all]')!.addEventListener('change',event=>{const checked=(event.target as HTMLInputElement).checked;pending.querySelectorAll<HTMLInputElement>('[data-registration-id]').forEach((box,index)=>box.checked=checked&&index<100);});
  for(const button of pending.querySelectorAll<HTMLButtonElement>('[data-review]'))button.addEventListener('click',()=>{
    const ids=Array.from(pending.querySelectorAll<HTMLInputElement>('[data-registration-id]:checked')).map(box=>box.dataset.registrationId!);
    if(!ids.length||ids.length>100){message(pending,'[data-review-message]','Chọn từ 1 đến 100 yêu cầu.');return;}
    const controls=pending.querySelectorAll<HTMLButtonElement>('[data-review]');controls.forEach(control=>control.disabled=true);
    void action(pending,'[data-review-message]',async()=>{try{const result=await api<{reviewed:number}>('admin/registrations/review',{ids,decision:button.dataset.review});await loadPending();await onReview();message(pending,'[data-review-message]',`Đã xử lý ${result.reviewed} yêu cầu.`);}finally{controls.forEach(control=>control.disabled=false);}});
  });
  const edit=pending.querySelector<HTMLFormElement>('[data-edit]')!;
  const province=edit.querySelector<HTMLSelectElement>('[data-edit-province]')!,unit=edit.querySelector<HTMLSelectElement>('[data-edit-unit]')!;
  let unitVersion=0;
  const loadUnits=async(selected?:string)=>{const version=++unitVersion;unit.replaceChildren();const reply=await api<Directory>(`admin/directory?provinceId=${encodeURIComponent(province.value)}`);if(version!==unitVersion)return;for(const item of reply.units)unit.add(new Option(item.name,item.id));if(selected)unit.value=selected;};
  pending.addEventListener('click',event=>{const button=(event.target as HTMLElement).closest<HTMLButtonElement>('[data-edit-registration]');if(button)void action(pending,'[data-review-message]',async()=>{const item=rows.find(row=>row.id===button.dataset.editRegistration)!;editing=item.id;const directory=await api<Directory>('admin/directory');province.replaceChildren();for(const root of directory.provinces)province.add(new Option(root.name,root.id));province.value=item.provinceId;await loadUnits(item.unitId);edit.hidden=false;edit.scrollIntoView({behavior:'smooth',block:'nearest'});});});
  province.addEventListener('change',()=>void action(pending,'[data-review-message]',()=>loadUnits()));
  edit.querySelector('[data-cancel-edit]')!.addEventListener('click',()=>{edit.hidden=true;editing=null;});
  edit.addEventListener('submit',event=>{event.preventDefault();if(editing)void action(pending,'[data-review-message]',async()=>{await api(`admin/registrations/${editing}/assignment`,{provinceId:province.value,unitId:unit.value});edit.hidden=true;editing=null;await loadPending();});});
  await Promise.all([loadLinks(),loadPending()]);
}
