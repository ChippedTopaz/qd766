import {installTriviaImport} from './admin-trivia-import.js';
import {confirmTriviaDeletion} from './admin-trivia-delete.js';
type Q={id:string;prompt:string;choices:string[];correctIndex:number;explanation:string;state:string;locked:boolean;revision:number;correctAttempts?:number;correctUsers?:number};
type Api=<T>(path:string,body?:unknown)=>Promise<T>;
const esc=(value:unknown)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function installTriviaBank(root:HTMLElement,api:Api):void{
  const section=document.createElement('section');section.dataset.triviaBank='true';
  section.innerHTML=`<h2>Ngân hàng Hỏi - đáp nhanh</h2><p>Đúng +1 điểm; sai đưa chuỗi đúng về 0. Điểm độc lập với Credit. Câu hỏi đã công khai được khóa nội dung; có thể thu hồi hoặc tạo câu mới.</p><p data-trivia-bank-status role="status">Mở mục này để tải ngân hàng câu hỏi.</p><button type="button" data-trivia-bank-new>Tạo câu hỏi</button><button type="button" data-trivia-bank-reload>Tải lại</button><form data-trivia-bank-form><label>Câu hỏi<textarea name="prompt" rows="3" maxlength="1000" minlength="5" required></textarea></label><div class="trivia-bank-choices">${[0,1,2,3,4,5].map(i=>`<label>Đáp án ${String.fromCharCode(65+i)}${i<2?'':' (tùy chọn)'}<input name="choice${i}" maxlength="400" ${i<2?'required':''}></label>`).join('')}</div><label>Đáp án đúng<select name="correct">${[0,1,2,3,4,5].map(i=>`<option value="${i}">${String.fromCharCode(65+i)}</option>`).join('')}</select></label><label>Giải thích sau khi trả lời<textarea name="explanation" rows="3" maxlength="2000"></textarea></label><label>Trạng thái<select name="state"><option value="draft">Nháp</option><option value="published">Công khai</option><option value="retired">Thu hồi</option></select></label><button class="primary" type="submit">Lưu câu hỏi</button></form><label class="trivia-bank-search">Tìm câu hỏi<input data-trivia-bank-search type="search" maxlength="200" placeholder="Nhập từ khóa câu hỏi…"></label><div data-trivia-bank-list class="table-wrap"></div><div class="actions"><button type="button" data-trivia-page-prev>Trang trước</button><span data-trivia-page-info></span><button type="button" data-trivia-page-next>Trang sau</button></div><div data-trivia-people-panel hidden></div>`;
  root.append(section);
  const form=section.querySelector<HTMLFormElement>('form')!;
  const input=(name:string)=>form.elements.namedItem(name) as HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement;
  const status=(text:string)=>{section.querySelector('[data-trivia-bank-status]')!.textContent=text};
  let questions:Q[]=[],selected:Q|null=null,loaded=false,busy=false,queued=false,editingForm=false,schemaAvailable=false,offset=0,total=0,peopleOffset=0,peopleId='',peopleTotal=0,peopleRevision=0;
  form.hidden=true;
  const size=100;
  async function removeQuestion(q:Q){busy=true;try{if(await confirmTriviaDeletion(q,api)){if(selected?.id===q.id){selected=null;editingForm=false;form.reset();form.hidden=true;}peopleRevision++;section.querySelector<HTMLElement>('[data-trivia-people-panel]')!.hidden=true;offset=0;busy=false;await load();status('Đã xóa câu hỏi và lịch sử trả lời. Điểm, chuỗi đúng và kỷ lục đã được cập nhật.');}}finally{busy=false;if(queued){queued=false;void load()}}}
  function renderList(){section.querySelector('[data-trivia-bank-list]')!.innerHTML=triviaBankRows(questions,offset);section.querySelector('[data-trivia-page-info]')!.textContent=`${total?offset+1:0}–${Math.min(offset+questions.length,total)} / ${total}`;section.querySelector<HTMLButtonElement>('[data-trivia-page-prev]')!.disabled=offset===0;section.querySelector<HTMLButtonElement>('[data-trivia-page-next]')!.disabled=offset+size>=total;}
  async function showPeople(id:string,page=0){peopleId=id;peopleOffset=page;const revision=++peopleRevision;const panel=section.querySelector<HTMLElement>('[data-trivia-people-panel]')!;panel.hidden=false;panel.textContent='Đang tải người trả lời đúng…';try{const body=await api<{total:number;users:CorrectUser[]}>(`admin/trivia/${encodeURIComponent(id)}/correct-users?offset=${page}&limit=${size}`);if(revision!==peopleRevision)return;peopleTotal=body.total;panel.innerHTML=`<h3>Người trả lời đúng</h3><p>${esc(questions.find(q=>q.id===id)?.prompt??'')} · ${body.total} người</p>${triviaCorrectUsers(body.users,page)}<div class="actions"><button type="button" data-trivia-people-prev ${page===0?'disabled':''}>Trang trước</button><button type="button" data-trivia-people-next ${page+size>=body.total?'disabled':''}>Trang sau</button><button type="button" data-trivia-people-close>Đóng</button></div>`;}catch(error){if(revision===peopleRevision)panel.textContent=(error as Error).message;}}
  function edit(q:Q|null){editingForm=true;form.hidden=!schemaAvailable;selected=q;form.reset();input('prompt').value=q?.prompt??'';input('correct').value=String(q?.correctIndex??0);input('explanation').value=q?.explanation??'';input('state').value=q?.state??'draft';
    for(let i=0;i<6;i++)input('choice'+i).value=q?.choices[i]??'';
    ['prompt','correct','explanation',...Array.from({length:6},(_,i)=>'choice'+i)].forEach(name=>input(name).disabled=Boolean(q?.locked));
    status(q?.locked?'Nội dung đã khóa. Chỉ thay đổi trạng thái công khai/thu hồi.':'Đang nhập bản nháp.');
  }
  async function load(){if(busy){queued=true;return}busy=true;status('Đang tải…');try{
    const query=section.querySelector<HTMLInputElement>('[data-trivia-bank-search]')!.value.trim();
    const body=await api<{available:boolean;questions:Q[];total:number}>(`admin/trivia?q=${encodeURIComponent(query)}&offset=${offset}&limit=${size}`);
    questions=body.questions;total=body.total;loaded=true;schemaAvailable=body.available;form.hidden=!schemaAvailable||!editingForm;renderList();
    status(body.available?`${total} câu hỏi phù hợp. Lượt đúng tính cả các lượt làm lại; danh sách người không trùng lặp.`:'Chưa nâng schema Trivia. Chưa thể lưu câu hỏi.');
  }catch(error){status((error as Error).message)}finally{busy=false;if(queued){queued=false;void load()}}}
  installTriviaImport(section,api,async()=>{offset=0;section.querySelector<HTMLInputElement>('[data-trivia-bank-search]')!.value='';await load()});
  let searchTimer:ReturnType<typeof setTimeout>;
  section.querySelector('[data-trivia-bank-search]')!.addEventListener('input',()=>{peopleRevision++;section.querySelector<HTMLElement>('[data-trivia-people-panel]')!.hidden=true;clearTimeout(searchTimer);searchTimer=setTimeout(()=>{offset=0;void load()},250)});
  section.addEventListener('click',event=>{
    const target=(event.target as HTMLElement).closest<HTMLButtonElement>('button');
    if(target?.hasAttribute('data-trivia-people-close')){peopleRevision++;section.querySelector<HTMLElement>('[data-trivia-people-panel]')!.hidden=true;return}
    if(target?.dataset.triviaPeople){void showPeople(target.dataset.triviaPeople);return}
    if(target?.hasAttribute('data-trivia-people-prev')&&peopleOffset>0){void showPeople(peopleId,peopleOffset-size);return}
    if(target?.hasAttribute('data-trivia-people-next')&&peopleOffset+size<peopleTotal){void showPeople(peopleId,peopleOffset+size);return}
    if(busy)return;
    if(target?.dataset.triviaDelete){const q=questions.find(q=>q.id===target.dataset.triviaDelete);if(q)void removeQuestion(q);return}
    if(target?.hasAttribute('data-trivia-page-prev')&&offset>0){offset-=size;void load();return}
    if(target?.hasAttribute('data-trivia-page-next')&&offset+size<total){offset+=size;void load();return}
const button=(event.target as HTMLElement).closest<HTMLButtonElement>('button');if(button?.hasAttribute('data-trivia-bank-new'))edit(null);if(button?.hasAttribute('data-trivia-bank-reload'))void load();if(button?.dataset.triviaEdit)edit(questions.find(q=>q.id===button.dataset.triviaEdit)??null);});
  form.addEventListener('submit',async event=>{event.preventDefault();if(busy)return;busy=true;const save=form.querySelector<HTMLButtonElement>('button[type=submit]')!;save.disabled=true;
    try{let choices=Array.from({length:6},(_,i)=>input('choice'+i).value.trim());while(choices.length>2&&!choices.at(-1))choices.pop();
      const q=await api<Q>('admin/trivia'+(selected?'/'+selected.id:''),{prompt:input('prompt').value,choices,correctIndex:Number(input('correct').value),explanation:input('explanation').value,state:input('state').value,revision:selected?.revision??0});
      edit(q);busy=false;await load();status('Đã lưu câu hỏi.');
    }catch(error){status((error as Error).message)}finally{busy=false;save.disabled=false}});
  root.addEventListener('click',event=>{if((event.target as HTMLElement).closest('[data-admin-section="trivia"]')&&!loaded)void load()});
}
type CorrectUser={id:string;name:string;email:string|null;correctAttempts:number;lastCorrectAt:string};
export function triviaBankRows(questions:Q[],offset=0):string{
  return '<table><thead><tr><th>STT</th><th>Câu hỏi</th><th>Trạng thái</th><th>Lượt đúng</th><th>Người đúng</th><th></th></tr></thead><tbody>'+questions.map((q,i)=>`<tr><td>${offset+i+1}</td><td>${esc(q.prompt)}</td><td>${esc({draft:'Nháp',published:'Công khai',retired:'Thu hồi'}[q.state]??q.state)}</td><td>${q.correctAttempts??0}</td><td><button type="button" data-trivia-people="${esc(q.id)}" aria-label="Xem người trả lời đúng câu ${offset+i+1}">${q.correctUsers??0} người · Xem</button></td><td><div class="actions"><button type="button" data-trivia-edit="${esc(q.id)}">Mở</button><button type="button" class="trivia-danger" data-trivia-delete="${esc(q.id)}" aria-label="Xóa câu hỏi ${offset+i+1}">Xóa</button></div></td></tr>`).join('')+(questions.length?'':'<tr><td colspan="6">Không có câu hỏi phù hợp.</td></tr>')+'</tbody></table>';
}
export function triviaCorrectUsers(users:CorrectUser[],offset=0):string{
  return '<div class="table-wrap"><table><thead><tr><th>STT</th><th>Người dùng</th><th>Email</th><th>Lượt đúng</th><th>Lần đúng gần nhất</th></tr></thead><tbody>'+users.map((u,i)=>`<tr><td>${offset+i+1}</td><td>${esc(u.name)}</td><td>${esc(u.email??'—')}</td><td>${u.correctAttempts}</td><td>${esc(new Date(u.lastCorrectAt).toLocaleString('vi-VN'))}</td></tr>`).join('')+(users.length?'':'<tr><td colspan="5">Chưa có người trả lời đúng.</td></tr>')+'</tbody></table></div>';
}
