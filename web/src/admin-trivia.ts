import {installTriviaImport} from './admin-trivia-import.js';
import {confirmTriviaDeletion} from './admin-trivia-delete.js';
type Q={id:string;prompt:string;choices:string[];correctIndex:number;explanation:string;state:string;locked:boolean;revision:number;correctAttempts?:number;correctUsers?:number};
type Api=<T>(path:string,body?:unknown)=>Promise<T>;
const esc=(value:unknown)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function installTriviaBank(root:HTMLElement,api:Api):void{
  const section=document.createElement('section');section.dataset.triviaBank='true';
  section.innerHTML=`<h2>Ngân hàng Hỏi - đáp nhanh</h2><p>Đúng +1 điểm; sai đưa chuỗi đúng về 0. Điểm độc lập với Credit. Câu hỏi đã công khai được khóa nội dung; có thể thu hồi hoặc tạo câu mới.</p>
    <p data-trivia-bank-status role="status">Mở mục này để tải ngân hàng câu hỏi.</p><button type="button" data-trivia-bank-new>Tạo câu hỏi</button><button type="button" data-trivia-bank-reload>Tải lại</button>
    <dialog class="trivia-question-dialog" aria-labelledby="trivia-question-title"><header><h2 id="trivia-question-title">Tạo câu hỏi</h2><button type="button" data-trivia-question-close aria-label="Đóng hộp thoại">✕</button></header><p data-trivia-question-status role="status" aria-live="polite"></p>
    <form data-trivia-bank-form><label>Câu hỏi<textarea name="prompt" rows="3" maxlength="1000" minlength="5" required></textarea></label>
    <div class="trivia-bank-choices">${[0,1,2].map(i=>`<label>Đáp án ${String.fromCharCode(65+i)}${i<2?'':' (tùy chọn)'}<input name="choice${i}" maxlength="400" ${i<2?'required':''}></label>`).join('')}</div>
    <label>Đáp án đúng<select name="correct">${[0,1,2].map(i=>`<option value="${i}">${String.fromCharCode(65+i)}</option>`).join('')}</select></label>
    <label>Giải thích sau khi trả lời<textarea name="explanation" rows="3" maxlength="2000"></textarea></label><label>Trạng thái<select name="state"><option value="draft">Nháp</option><option value="published">Công khai</option><option value="retired">Thu hồi</option></select></label><footer class="trivia-question-actions"><button type="button" data-trivia-question-close>Hủy</button><button class="primary" type="submit">Lưu câu hỏi</button></footer></form></dialog>
    <div class="trivia-bank-filters"><label class="trivia-bank-search">Tìm câu hỏi<input data-trivia-bank-search type="search" maxlength="200" placeholder="Nhập từ khóa câu hỏi…"></label></div><div data-trivia-bank-list class="table-wrap"></div>
    <div class="actions"><button type="button" data-trivia-page-prev>Trang trước</button><span data-trivia-page-info></span><button type="button" data-trivia-page-next>Trang sau</button></div><div data-trivia-people-panel hidden></div>`;
  root.append(section);
  const form=section.querySelector<HTMLFormElement>('form')!;
  const input=(name:string)=>form.elements.namedItem(name) as HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement;
  const status=(text:string)=>{section.querySelector('[data-trivia-bank-status]')!.textContent=text};
  const dialog=section.querySelector<HTMLDialogElement>('.trivia-question-dialog')!;
  const editorStatus=(text:string)=>{dialog.querySelector('[data-trivia-question-status]')!.textContent=text};
  let questions:Q[]=[],selected:Q|null=null,loaded=false,busy=false,queued=false,saving=false,schemaAvailable:boolean|null=null,loadError='',offset=0,total=0,peopleOffset=0,peopleId='',peopleTotal=0,peopleRevision=0;
  dialog.addEventListener('cancel',event=>{if(saving)event.preventDefault()});
  dialog.addEventListener('close',()=>{selected=null;form.reset()});
  const size=10,peoplePageSize=100;
  const stateFilter=document.createElement('label');stateFilter.className='trivia-bank-search';stateFilter.innerHTML='<span>Trạng thái</span><select data-trivia-bank-state><option value="">Tất cả</option><option value="published">Công khai</option><option value="draft">Nháp</option><option value="retired">Thu hồi</option></select>';
  section.querySelector('.trivia-bank-filters')!.append(stateFilter);
  // Only A–C for new/editable questions. Keep locked legacy question contents intact.
  stateFilter.querySelector('select')!.addEventListener('change',()=>{peopleRevision++;section.querySelector<HTMLElement>('[data-trivia-people-panel]')!.hidden=true;offset=0;void load()});
  async function publishQuestion(q:Q){
    busy=true;section.querySelectorAll<HTMLButtonElement>('[data-trivia-publish]').forEach(button=>button.disabled=true);
    try{const saved=await api<Q>(`admin/trivia/${encodeURIComponent(q.id)}/publish`,{revision:q.revision});if(selected?.id===q.id)edit(saved);busy=false;await load();status('Đã duyệt công khai và lưu câu hỏi.');}
    catch(error){status((error as Error).message)}finally{busy=false;section.querySelectorAll<HTMLButtonElement>('[data-trivia-publish]').forEach(button=>button.disabled=false);if(queued){queued=false;void load()}}
  }
  async function removeQuestion(q:Q){busy=true;try{if(await confirmTriviaDeletion(q,api)){if(selected?.id===q.id){dialog.close();selected=null;form.reset();}peopleRevision++;section.querySelector<HTMLElement>('[data-trivia-people-panel]')!.hidden=true;offset=0;busy=false;await load();status('Đã xóa câu hỏi và lịch sử trả lời. Điểm, chuỗi đúng và kỷ lục đã được cập nhật.');}}finally{busy=false;if(queued){queued=false;void load()}}}
  function renderList(){section.querySelector('[data-trivia-bank-list]')!.innerHTML=triviaBankRows(questions,offset);section.querySelector('[data-trivia-page-info]')!.textContent=`${total?offset+1:0}–${Math.min(offset+questions.length,total)} / ${total}`;section.querySelector<HTMLButtonElement>('[data-trivia-page-prev]')!.disabled=offset===0;section.querySelector<HTMLButtonElement>('[data-trivia-page-next]')!.disabled=offset+size>=total;}
  async function showPeople(id:string,page=0){peopleId=id;peopleOffset=page;const revision=++peopleRevision;const panel=section.querySelector<HTMLElement>('[data-trivia-people-panel]')!;panel.hidden=false;panel.textContent='Đang tải người trả lời đúng…';try{const body=await api<{total:number;users:CorrectUser[]}>(`admin/trivia/${encodeURIComponent(id)}/correct-users?offset=${page}&limit=${peoplePageSize}`);if(revision!==peopleRevision)return;peopleTotal=body.total;panel.innerHTML=`<h3>Người trả lời đúng</h3><p>${esc(questions.find(q=>q.id===id)?.prompt??'')} · ${body.total} người</p>${triviaCorrectUsers(body.users,page)}<div class="actions"><button type="button" data-trivia-people-prev ${page===0?'disabled':''}>Trang trước</button><button type="button" data-trivia-people-next ${page+peoplePageSize>=body.total?'disabled':''}>Trang sau</button><button type="button" data-trivia-people-close>Đóng</button></div>`;}catch(error){if(revision===peopleRevision)panel.textContent=(error as Error).message;}}
  function edit(q:Q|null){if(schemaAvailable!==true){status(schemaAvailable===false?'Chưa nâng schema Trivia. Chưa thể lưu câu hỏi.':loadError||'Chưa tải được ngân hàng câu hỏi. Vui lòng bấm Tải lại.');return}selected=q;form.reset();input('prompt').value=q?.prompt??'';input('correct').value=String(q?.correctIndex??0);input('explanation').value=q?.explanation??'';input('state').value=q?.state??'draft';
    for(let i=0;i<3;i++)input('choice'+i).value=q?.choices[i]??'';
    ['prompt','correct','explanation',...Array.from({length:3},(_,i)=>'choice'+i)].forEach(name=>input(name).disabled=Boolean(q?.locked));
    dialog.querySelector('h2')!.textContent=q?(q.locked?'Chi tiết câu hỏi':'Sửa câu hỏi'):'Tạo câu hỏi';
    editorStatus(q?.locked?'Nội dung đã khóa. Chỉ thay đổi trạng thái công khai/thu hồi.':'Nhập câu hỏi và 2–3 đáp án.');
    if(!dialog.open)dialog.showModal();input(q?.locked?'state':'prompt').focus();
  }
  async function load(){if(busy){queued=true;return}busy=true;status('Đang tải…');try{
    const query=section.querySelector<HTMLInputElement>('[data-trivia-bank-search]')!.value.trim();
    const state=stateFilter.querySelector<HTMLSelectElement>('select')!.value;
    let body=await api<{available:boolean;questions:Q[];total:number}>(`admin/trivia?q=${encodeURIComponent(query)}&offset=${offset}&limit=${size}${state?'&state='+encodeURIComponent(state):''}`);
    if(body.available&&offset>0&&offset>=body.total){offset=Math.max(0,Math.floor((body.total-1)/size)*size);body=await api(`admin/trivia?q=${encodeURIComponent(query)}&offset=${offset}&limit=${size}${state?'&state='+encodeURIComponent(state):''}`);}
    questions=body.questions;total=body.total;loaded=true;loadError='';schemaAvailable=body.available;renderList();
    status(body.available?`${total} câu hỏi phù hợp. Lượt đúng tính cả các lượt làm lại; danh sách người không trùng lặp.`:'Chưa nâng schema Trivia. Chưa thể lưu câu hỏi.');
  }catch(error){loaded=false;schemaAvailable=null;loadError=(error as Error).message;status(loadError)}finally{busy=false;if(queued){queued=false;void load()}}}
  installTriviaImport(section,api,async()=>{offset=0;section.querySelector<HTMLInputElement>('[data-trivia-bank-search]')!.value='';await load()});
  let searchTimer:ReturnType<typeof setTimeout>;
  section.querySelector('[data-trivia-bank-search]')!.addEventListener('input',()=>{peopleRevision++;section.querySelector<HTMLElement>('[data-trivia-people-panel]')!.hidden=true;clearTimeout(searchTimer);searchTimer=setTimeout(()=>{offset=0;void load()},250)});
  section.addEventListener('click',event=>{
    const target=(event.target as HTMLElement).closest<HTMLButtonElement>('button');
    if(target?.hasAttribute('data-trivia-question-close')){if(!saving)dialog.close();return}
    if(target?.hasAttribute('data-trivia-people-close')){peopleRevision++;section.querySelector<HTMLElement>('[data-trivia-people-panel]')!.hidden=true;return}
    if(target?.dataset.triviaPeople){void showPeople(target.dataset.triviaPeople);return}
    if(target?.hasAttribute('data-trivia-people-prev')&&peopleOffset>0){void showPeople(peopleId,peopleOffset-peoplePageSize);return}
    if(target?.hasAttribute('data-trivia-people-next')&&peopleOffset+peoplePageSize<peopleTotal){void showPeople(peopleId,peopleOffset+peoplePageSize);return}
    if(busy)return;
    if(target?.dataset.triviaPublish){const q=questions.find(q=>q.id===target.dataset.triviaPublish);if(q?.state==='draft')void publishQuestion(q);return}
    if(target?.dataset.triviaDelete){const q=questions.find(q=>q.id===target.dataset.triviaDelete);if(q)void removeQuestion(q);return}
    if(target?.hasAttribute('data-trivia-page-prev')&&offset>0){offset-=size;void load();return}
    if(target?.hasAttribute('data-trivia-page-next')&&offset+size<total){offset+=size;void load();return}
const button=(event.target as HTMLElement).closest<HTMLButtonElement>('button');if(button?.hasAttribute('data-trivia-bank-new'))edit(null);if(button?.hasAttribute('data-trivia-bank-reload'))void load();if(button?.dataset.triviaEdit)edit(questions.find(q=>q.id===button.dataset.triviaEdit)??null);});
  form.addEventListener('submit',async event=>{event.preventDefault();if(busy)return;busy=true;saving=true;const save=form.querySelector<HTMLButtonElement>('button[type=submit]')!;save.disabled=true;dialog.querySelectorAll<HTMLButtonElement>('[data-trivia-question-close]').forEach(button=>button.disabled=true);editorStatus('Đang lưu câu hỏi…');
    try{let choices=Array.from({length:3},(_,i)=>input('choice'+i).value.trim());while(choices.length>2&&!choices.at(-1))choices.pop();
      const content=selected?.locked?{prompt:selected.prompt,choices:selected.choices,correctIndex:selected.correctIndex,explanation:selected.explanation}:{prompt:input('prompt').value,choices,correctIndex:Number(input('correct').value),explanation:input('explanation').value};
      await api<Q>('admin/trivia'+(selected?'/'+selected.id:''),{...content,state:input('state').value,revision:selected?.revision??0});
      dialog.close();selected=null;busy=false;await load();status('Đã lưu câu hỏi.');
    }catch(error){editorStatus((error as Error).message)}finally{busy=false;saving=false;save.disabled=false;dialog.querySelectorAll<HTMLButtonElement>('[data-trivia-question-close]').forEach(button=>button.disabled=false);if(queued){queued=false;void load()}}});
  root.addEventListener('click',event=>{if((event.target as HTMLElement).closest('[data-admin-section="trivia"]')&&!loaded)void load()});
}
type CorrectUser={id:string;name:string;email:string|null;correctAttempts:number;lastCorrectAt:string};
export function triviaBankRows(questions:Q[],offset=0):string{
  return '<table><thead><tr><th>STT</th><th>Câu hỏi</th><th>Trạng thái</th><th>Lượt đúng</th><th>Người đúng</th><th></th></tr></thead><tbody>'+questions.map((q,i)=>`<tr><td>${offset+i+1}</td><td>${esc(q.prompt)}</td><td>${esc({draft:'Nháp',published:'Công khai',retired:'Thu hồi'}[q.state]??q.state)}</td><td>${q.correctAttempts??0}</td><td><button type="button" data-trivia-people="${esc(q.id)}" aria-label="Xem người trả lời đúng câu ${offset+i+1}">${q.correctUsers??0} người · Xem</button></td><td><div class="actions">${q.state==='draft'?`<button type="button" data-trivia-publish="${esc(q.id)}">Duyệt công khai</button>`:''}<button type="button" data-trivia-edit="${esc(q.id)}">Mở</button><button type="button" class="trivia-danger" data-trivia-delete="${esc(q.id)}" aria-label="Xóa câu hỏi ${offset+i+1}">Xóa</button></div></td></tr>`).join('')+(questions.length?'':'<tr><td colspan="6">Không có câu hỏi phù hợp.</td></tr>')+'</tbody></table>';
}
export function triviaCorrectUsers(users:CorrectUser[],offset=0):string{
  return '<div class="table-wrap"><table><thead><tr><th>STT</th><th>Người dùng</th><th>Email</th><th>Lượt đúng</th><th>Lần đúng gần nhất</th></tr></thead><tbody>'+users.map((u,i)=>`<tr><td>${offset+i+1}</td><td>${esc(u.name)}</td><td>${esc(u.email??'—')}</td><td>${u.correctAttempts}</td><td>${esc(new Date(u.lastCorrectAt).toLocaleString('vi-VN'))}</td></tr>`).join('')+(users.length?'':'<tr><td colspan="5">Chưa có người trả lời đúng.</td></tr>')+'</tbody></table></div>';
}
