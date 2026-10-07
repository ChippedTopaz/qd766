type Api=<T>(path:string,body?:unknown)=>Promise<T>;
interface Configuration {version:number;activeVersion:number;guidance:string;knowledge:string;defaultGuidance:string;schemaReady:boolean;rules:string[];history:{version:number;note:string;at:string;actor:string}[]}
const esc=(value:unknown)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function installAnalysisConfiguration(root:HTMLElement,api:Api):void {
  const section=document.createElement('section');section.dataset.analysisConfiguration='true';
  section.innerHTML=`<h2>Cấu hình phân tích AI</h2><p>Hướng dẫn và kiến thức nghiệp vụ dùng chung cho các lượt phân tích mới. Không thay đổi kết quả đã lưu hoặc lượt đang chờ.</p><p id="ai-config-status" role="status">Mở mục này để tải cấu hình.</p><form id="ai-config-form"><label>Hướng dẫn phân tích<textarea id="ai-config-guidance" rows="8" minlength="20" maxlength="10000" required placeholder="Cách phân tích, mức độ chi tiết, cách đưa ra khuyến nghị…"></textarea></label><label>Kiến thức nghiệp vụ đã duyệt<textarea id="ai-config-knowledge" rows="12" maxlength="30000" placeholder="Quy tắc theo nhóm chỉ tiêu, điều kiện áp dụng, ngoại lệ và ví dụ phân tích tốt. Ghi rõ nguồn và ngày đối chiếu nếu có."></textarea></label><p class="ai-config-hint">Chỉ nhập kiến thức đã kiểm chứng. Không dán API key, mật khẩu, dữ liệu cá nhân hoặc danh sách hồ sơ. Gemini trên web không tự đồng bộ vào đây.</p><label>Ghi chú thay đổi<input id="ai-config-note" minlength="3" maxlength="500" required placeholder="Mô tả nội dung đã bổ sung hoặc chỉnh sửa"></label><div class="actions"><button class="primary" id="ai-config-save" disabled>Lưu cấu hình</button><button type="button" id="ai-config-default" disabled>Khôi phục mặc định vào bản nháp</button><button type="button" id="ai-config-reload">Tải lại cấu hình hiện hành</button></div></form><details class="ai-config-rules"><summary>Nguyên tắc hệ thống — không thể thay đổi tại đây</summary><ul id="ai-config-rules"></ul><p>API key, model, mức Credit và hàng chờ không được chỉnh bằng nội dung hướng dẫn.</p></details><div class="ai-config-history"><h3>Lịch sử phiên bản</h3><label>Phiên bản đã lưu<select id="ai-config-version" disabled></select></label><button type="button" id="ai-config-load-version" disabled>Đưa phiên bản vào bản nháp</button><p>Xem hoặc khôi phục chỉ tạo bản nháp. Bấm Lưu cấu hình mới áp dụng; mọi phiên bản đã lưu được giữ lại.</p></div>`;
  root.append(section);
  const get=<T extends HTMLElement>(id:string)=>section.querySelector<T>('#'+id)!;
  const status=(text:string)=>{get('ai-config-status').textContent=text;};
  let configuration:Configuration|null=null,busy=false,loaded=false;
  const setBusy=(value:boolean)=>{
    busy=value;section.setAttribute('aria-busy',String(value));
    ['save','default','load-version'].forEach(name=>{get<HTMLButtonElement>('ai-config-'+name).disabled=value||!configuration||(name==='save'&&!configuration.schemaReady);});
    get<HTMLButtonElement>('ai-config-reload').disabled=value;
    get<HTMLSelectElement>('ai-config-version').disabled=value||!configuration;
  };
  const fill=(value:Configuration)=>{
    configuration=value;loaded=true;
    get<HTMLTextAreaElement>('ai-config-guidance').value=value.guidance;
    get<HTMLTextAreaElement>('ai-config-knowledge').value=value.knowledge;
    get<HTMLInputElement>('ai-config-note').value='';
    get('ai-config-rules').innerHTML=value.rules.map(rule=>`<li>${esc(rule)}</li>`).join('');
    get<HTMLSelectElement>('ai-config-version').innerHTML=value.history.map(row=>`<option value="${row.version}">Phiên bản ${row.version} · ${esc(new Date(row.at).toLocaleString('vi-VN'))} · ${esc(row.actor)} · ${esc(row.note)}</option>`).join('')+'<option value="0">Mặc định hệ thống</option>';
    if(value.history.some(row=>row.version===value.version))get<HTMLSelectElement>('ai-config-version').value=String(value.version);
    status(value.schemaReady?`Đang xem phiên bản ${value.version}. Phiên bản áp dụng: ${value.activeVersion}.`:'Đang dùng mặc định. Cần nâng schema cấu hình AI trước khi lưu.');
  };
  const load=async(version?:number)=>{
    if(busy)return;setBusy(true);status('Đang tải cấu hình…');
    try{fill(await api<Configuration>('admin/analysis-configuration'+(version===undefined?'':'?version='+version)));}
    catch(error){status(error instanceof Error?error.message:'Không tải được cấu hình.');}
    finally{setBusy(false);}
  };
  root.addEventListener('click',event=>{const key=(event.target as HTMLElement).closest<HTMLElement>('[data-admin-section]')?.dataset.adminSection;if(key==='ai-configuration'&&!loaded)void load();});
  get('ai-config-reload').addEventListener('click',()=>void load());
  get('ai-config-default').addEventListener('click',()=>{
    if(busy||!configuration)return;
    get<HTMLTextAreaElement>('ai-config-guidance').value=configuration.defaultGuidance;
    get<HTMLTextAreaElement>('ai-config-knowledge').value='';
    get<HTMLInputElement>('ai-config-note').value='Khôi phục cấu hình mặc định';
    status('Đã đưa mặc định vào bản nháp. Chưa thay đổi cấu hình đang áp dụng.');
  });
  get('ai-config-load-version').addEventListener('click',()=>void load(Number(get<HTMLSelectElement>('ai-config-version').value)));
  get('ai-config-form').addEventListener('submit',event=>{
    event.preventDefault();if(busy||!configuration?.schemaReady)return;
    const payload={expectedVersion:configuration.activeVersion,guidance:get<HTMLTextAreaElement>('ai-config-guidance').value,knowledge:get<HTMLTextAreaElement>('ai-config-knowledge').value,note:get<HTMLInputElement>('ai-config-note').value};
    void (async()=>{setBusy(true);status('Đang lưu cấu hình…');
      try{
        const result=await api<{version:number;message:string}>('admin/analysis-configuration',payload);
        // Keep the new version immediately, even if the following read loses connectivity.
        configuration!.activeVersion=result.version;
        status(result.message);fill(await api<Configuration>('admin/analysis-configuration'));
        status(`Đã lưu phiên bản ${result.version}. Áp dụng cho lượt xác nhận mới; không cần restart backend.`);
      }catch(error){status(error instanceof Error?error.message:'Không xác nhận được kết quả lưu. Tải lại trước khi gửi lại.');}
      finally{setBusy(false);}
    })();
  });
}
