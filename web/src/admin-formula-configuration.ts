import {defaultFormulaConfiguration,displayedFormulas,formulaCard,formulaDisplayCode,type Formula,type FormulaConfiguration} from './formula-reference.js';
import {groupColors,groupIcon} from './bento.js';
import {highlightFormulaPreview,businessEditorLines,updateBusinessEditor} from './admin-formula-focus.js';
type Api=<T>(path:string,body?:unknown)=>Promise<T>;
interface Saved {version:number;activeVersion:number;schemaReady:boolean;configuration:FormulaConfiguration;history:{version:number;note:string;actor:string;at:string}[]}
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function installFormulaConfiguration(root:HTMLElement,api:Api):void {
 const section=document.createElement('section');section.dataset.formulaConfiguration='true';section.className='formula-admin';
 section.innerHTML=`<div class="formula-admin-heading"><div><h2>Công thức tính</h2><p>Chỉnh nội dung tra cứu. Không thay đổi điểm đã thu thập hoặc logic tính điểm.</p></div><span data-formula-version></span></div><p data-formula-status role="status">Mở mục này để tải toàn bộ nội dung hiện tại.</p><div data-formula-work hidden><div class="formula-admin-layout"><div class="formula-admin-editor"><div class="formula-admin-groups" data-formula-groups aria-label="Chọn nhóm chỉ tiêu"></div><div class="formula-admin-toolbar"><label>Chỉ tiêu<select data-formula-item></select></label></div><form data-formula-form><div class="formula-admin-fields"><label>Tên chỉ tiêu<input data-field="title" required maxlength="2000"></label><div class="formula-admin-three"><label>Điểm tối đa<input data-field="maximum" type="number" min="0" max="100" step="any" placeholder="Chưa xác định"></label><label>Ngưỡng đạt (%)<input data-field="target" type="number" min="0.01" max="100" step="any" placeholder="Không có ngưỡng"></label><label>Tên tỷ lệ<input data-field="equationLabel" required></label></div><p class="formula-admin-scoring-hint" data-formula-scoring-hint></p><details open><summary>Công thức toán học</summary><div class="formula-admin-fraction-fields"><label>Tử số / biểu thức<textarea data-field="numerator" rows="2" required></textarea></label><label>Mẫu số<textarea data-field="denominator" rows="2"></textarea></label></div><label>Hệ số / phép nhân<input data-field="multiplier"></label><div data-formula-extras></div><button type="button" data-formula-add-equation>+ Công thức bổ sung</button></details><details open><summary>Mô tả nghiệp vụ</summary><label>Nội dung nghiệp vụ<textarea data-field="businessLines" rows="10"></textarea></label><small>Mỗi dòng là một đoạn. Giữ nguyên ý nghĩa, điều kiện và ngoại lệ khi sửa.</small></details><details><summary>Nguồn dữ liệu</summary><label>Nội dung nguồn<textarea data-field="dataSources" rows="5"></textarea></label></details><details><summary>Lưu ý khi đánh giá</summary><label>Lưu ý nghiệp vụ<textarea data-field="notes" rows="6"></textarea></label></details></div><div class="formula-admin-save"><label>Ghi chú thay đổi<input data-formula-note minlength="3" maxlength="500" required placeholder="Nội dung cập nhật và căn cứ"></label><div class="actions"><button class="primary" data-formula-save>Lưu thay đổi</button><button type="button" data-formula-reload>Tải lại bản đang áp dụng</button></div></div></form></div><aside class="formula-admin-preview" data-formula-preview><h3>Xem trước chỉ tiêu</h3><p class="formula-preview-context" data-formula-preview-context></p><div data-formula-card></div></aside></div><details class="formula-admin-history"><summary>Lịch sử phiên bản</summary><label>Phiên bản<select data-formula-history></select></label><button type="button" data-formula-restore>Đưa phiên bản vào bản nháp</button><p>Chưa áp dụng ngay. Kiểm tra và bấm Lưu thay đổi để khôi phục. Các phiên bản cũ được giữ lại.</p></details></div>`;
 root.append(section);
 const get=<T extends HTMLElement>(selector:string)=>section.querySelector<T>(selector)!;
 let saved:Saved|null=null,draft=defaultFormulaConfiguration(),groupId=draft.groups[0]!.id,itemId='1.1',busy=false,dirty=false,loaded=false;
 let activeEditor:HTMLElement|null=null;
 const status=(v:string)=>{get('[data-formula-status]').textContent=v;};
 const group=()=>draft.groups.find(g=>g.id===groupId)!;
 const item=()=>group().items.find(i=>i.id===itemId)!;
 const field=<T extends HTMLInputElement|HTMLTextAreaElement>(name:string)=>get<T>(`[data-field="${name}"]`);
 const lines=(text:string,original:string[])=>text===original.join('\n')?original:text.split('\n');
 function mark(){dirty=!!saved&&JSON.stringify(draft)!==JSON.stringify(saved.configuration);get('[data-formula-version]').textContent=`Phiên bản ${saved?.activeVersion??0}${dirty?' · Chưa lưu':''}`;}
 function remember(){
  if(!loaded)return;
  const f=item();
  for(const name of ['title','equationLabel','numerator','denominator','multiplier'] as const)f[name]=field(name).value;
  for(const name of ['maximum','target'] as const)f[name]=field(name).value===''?null:Number(field(name).value);
  updateBusinessEditor(f,field('businessLines').value);f.document.notes=lines(field('notes').value,f.document.notes);f.document.dataSources=lines(field('dataSources').value,f.document.dataSources);
  f.extras=Array.from(section.querySelectorAll<HTMLElement>('[data-extra-row]')).map((row,index)=>{const previous=f.extras?.[index],operator=row.querySelector<HTMLSelectElement>('[data-extra="operator"]')!.value as 'add'|'subtract'|'multiply'|'divide',multiplier=row.querySelector<HTMLInputElement>('[data-extra="multiplier"]')!.value;return {label:row.querySelector<HTMLInputElement>('[data-extra="label"]')!.value,numerator:row.querySelector<HTMLTextAreaElement>('[data-extra="numerator"]')!.value,denominator:row.querySelector<HTMLTextAreaElement>('[data-extra="denominator"]')!.value,...(previous?.operator!==undefined||operator!=='divide'?{operator}:{}),...(previous?.multiplier!==undefined||multiplier!=='× 100%'?{multiplier}:{})};});
  mark();
 }
 function preview(){
  const f=item(),panel=get('[data-formula-preview]');
  const expanded=Array.from(panel.querySelectorAll<HTMLDetailsElement>('details[open]')).map(el=>el.className);
  get('[data-formula-card]').innerHTML=formulaCard(groupId,f);
  panel.querySelectorAll<HTMLDetailsElement>('details').forEach(el=>{if(expanded.includes(el.className))el.open=true;});
  get('[data-formula-preview-context]').innerHTML=`<span data-preview-group-name>${esc(group().name)}</span> · <span data-preview-group-maximum>${group().maximum} điểm tối đa</span>`;
  get('[data-formula-scoring-hint]').textContent=f.target
   ?'Có ngưỡng: đạt ngưỡng được điểm tối đa; dưới ngưỡng, điểm = tỷ lệ / ngưỡng × điểm tối đa.'
   :'Không có ngưỡng: điểm = tỷ lệ (%) / 100 × điểm tối đa. Để trống điểm tối đa nếu chưa xác định.';
  highlightFormulaPreview(panel,activeEditor,f);
 }
 function options(){
  const items=displayedFormulas(group());
  get<HTMLSelectElement>('[data-formula-item]').innerHTML=items.map(f=>`<option value="${f.id}">${formulaDisplayCode(f.id)} · ${esc(f.title)}</option>`).join('');get<HTMLSelectElement>('[data-formula-item]').value=itemId;
 }
 function fill(){
  activeEditor=null;
  const f=item();
  section.querySelectorAll<HTMLInputElement|HTMLTextAreaElement>('[data-field]').forEach(el=>{
   const name=el.dataset.field!;let value:unknown=name==='businessLines'?businessEditorLines(f):name==='notes'||name==='dataSources'?f.document[name]:f[name as keyof Formula];
   el.value=Array.isArray(value)?value.join('\n'):String(value??'');
  });
  get('[data-formula-extras]').innerHTML=(f.extras??[]).map((e,index)=>`<div class="formula-admin-extra" data-extra-row><strong>Công thức phụ ${index+1}</strong><button type="button" data-extra-remove="${index}" aria-label="Bỏ công thức bổ sung">×</button><label>Tên<input data-extra="label" value="${esc(e.label)}"></label><label>Phép tính<select data-extra="operator">${([['add','Cộng (+)'],['subtract','Trừ (−)'],['multiply','Nhân (×)'],['divide','Chia (÷)']] as const).map(([value,label])=>`<option value="${value}" ${value===(e.operator??'divide')?'selected':''}>${label}</option>`).join('')}</select></label><div class="formula-admin-fraction-fields"><label>Thành phần thứ nhất / Tử số<textarea data-extra="numerator" rows="2">${esc(e.numerator)}</textarea></label><label>Thành phần thứ hai / Mẫu số<textarea data-extra="denominator" rows="2">${esc(e.denominator)}</textarea></label></div><label>Hệ số / phép nhân tiếp theo<input data-extra="multiplier" value="${esc(e.multiplier??'× 100%')}" placeholder="Để trống nếu không cần"></label></div>`).join('');
  get('[data-formula-groups]').innerHTML=draft.groups.map(g=>`<button type="button" data-formula-admin-group="${g.id}" aria-pressed="${g.id===groupId}" style="--group-color:${groupColors[g.id]}">${groupIcon(g.id)}<span>${esc(g.name)}</span><strong>${g.maximum}</strong></button>`).join('');options();preview();mark();
 }
 function setBusy(value:boolean){busy=value;section.setAttribute('aria-busy',String(value));section.querySelectorAll<HTMLInputElement|HTMLTextAreaElement|HTMLSelectElement|HTMLButtonElement>('input,textarea,select,button').forEach(el=>el.disabled=value);get<HTMLButtonElement>('[data-formula-save]').disabled=value||!saved?.schemaReady;}
 async function load(){
  if(busy)return;setBusy(true);
  try{saved=await api<Saved>('admin/formula-configuration');draft=structuredClone(saved.configuration);loaded=true;get('[data-formula-work]').hidden=false;fill();get<HTMLInputElement>('[data-formula-note]').value='';get<HTMLSelectElement>('[data-formula-history]').innerHTML=saved.history.map(r=>`<option value="${r.version}">#${r.version} · ${esc(r.note)} · ${esc(r.actor)} · ${esc(new Date(r.at).toLocaleString('vi-VN'))}</option>`).join('')+'<option value="0">Bản gốc nguyên trạng</option>';status(saved.schemaReady?'Đã tải đủ 6 nhóm. Chọn chỉ tiêu để chỉnh sửa.':'Chưa nâng schema Công thức tính: có thể xem và soạn, chưa thể lưu.');}
  catch(e){status(e instanceof Error?e.message:String(e));}finally{setBusy(false);}
 }
 section.addEventListener('input',()=>{if(!busy&&loaded){remember();preview();}});
 section.addEventListener('change',event=>{if((event.target as HTMLElement).hasAttribute('data-extra')&&!busy&&loaded){remember();preview();}});
 const focusPreview=(event:Event)=>{
  const editor=event.target;
  if(!(editor instanceof HTMLElement)||!editor.closest('[data-formula-form]')||editor.closest('[data-formula-preview]'))return;
  activeEditor=editor;highlightFormulaPreview(get('[data-formula-preview]'),activeEditor,item());
 };
 section.addEventListener('focusin',focusPreview);
 section.addEventListener('click',focusPreview);
 section.addEventListener('keyup',focusPreview);
 section.addEventListener('select',focusPreview,true);
 get<HTMLSelectElement>('[data-formula-item]').addEventListener('change',event=>{remember();itemId=(event.target as HTMLSelectElement).value;fill();});
 section.addEventListener('click',event=>{
  const button=(event.target as HTMLElement).closest<HTMLButtonElement>('button');if(!button||busy)return;
  if(button.dataset.formulaAdminGroup){remember();groupId=button.dataset.formulaAdminGroup as typeof groupId;itemId=displayedFormulas(group())[0]!.id;fill();}
  if(button.hasAttribute('data-formula-add-equation')){remember();item().extras!.push({label:'',numerator:'',denominator:'',operator:'divide',multiplier:''});fill();}
  if(button.dataset.extraRemove!==undefined){remember();item().extras!.splice(Number(button.dataset.extraRemove),1);fill();}
  if(button.hasAttribute('data-formula-reload')){if(dirty){status('Có bản nháp chưa lưu. Bấm lại Tải lại bản đang áp dụng để bỏ bản nháp.');if(button.dataset.confirmDiscard!=='true'){button.dataset.confirmDiscard='true';return;}}delete button.dataset.confirmDiscard;void load();}
 });
 get('[data-formula-restore]').addEventListener('click',()=>{void (async()=>{if(busy||!saved)return;setBusy(true);try{const revision=await api<Saved>('admin/formula-configuration?version='+get<HTMLSelectElement>('[data-formula-history]').value);draft=structuredClone(revision.configuration);fill();get<HTMLInputElement>('[data-formula-note]').value='Khôi phục nội dung phiên bản '+revision.version;status('Đã đưa phiên bản vào bản nháp. Kiểm tra rồi Lưu thay đổi để áp dụng.');}catch(e){status(String(e));}finally{setBusy(false);}})();});
 get('[data-formula-form]').addEventListener('submit',event=>{event.preventDefault();void (async()=>{if(busy||!saved?.schemaReady)return;remember();setBusy(true);try{const result=await api<{version:number;message:string}>('admin/formula-configuration',{expectedVersion:saved.activeVersion,configuration:draft,note:get<HTMLInputElement>('[data-formula-note]').value});setBusy(false);await load();status(result.message);}catch(e){status(e instanceof Error?e.message:String(e));}finally{setBusy(false);}})();});
 root.addEventListener('click',event=>{if((event.target as HTMLElement).closest<HTMLElement>('[data-admin-section]')?.dataset.adminSection==='formulas'&&!loaded)void load();});
 window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
}
