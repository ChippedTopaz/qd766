type Api=<T>(path:string,body?:unknown)=>Promise<T>;
type Report={valid:boolean;newCount:number;saved:number;errors:{row:number;message:string}[];duplicates:{row:number;prompt:string}[];questions:{row:number;prompt:string;choices:string[];correctIndex:number;explanation:string}[]};
const esc=(v:unknown)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function importReport(report:Report):string{
  return `<p><strong>${report.newCount} câu mới</strong> · ${report.duplicates.length} câu trùng bỏ qua · ${report.errors.length} dòng lỗi</p>`+
    (report.errors.length?`<ul>${report.errors.map(e=>`<li>Dòng ${e.row}: ${esc(e.message)}</li>`).join('')}</ul>`:'')+
    (report.duplicates.length?`<details><summary>Các câu trùng</summary><ul>${report.duplicates.map(q=>`<li>Dòng ${q.row}: ${esc(q.prompt)}</li>`).join('')}</ul></details>`:'')+
    (report.questions.length?`<details open><summary>Xem trước câu hỏi mới</summary><div class="table-wrap"><table><thead><tr><th>Dòng Excel</th><th>Câu hỏi và đáp án</th><th>Đáp án đúng</th><th>Giải thích</th></tr></thead><tbody>${report.questions.map(q=>`<tr><td>${q.row}</td><td><strong>${esc(q.prompt)}</strong>${q.choices.map((c,i)=>`<div>${String.fromCharCode(65+i)}. ${esc(c)}</div>`).join('')}</td><td>${String.fromCharCode(65+q.correctIndex)}</td><td>${esc(q.explanation)||'—'}</td></tr>`).join('')}</tbody></table></div></details>`:'');
}
export function installTriviaImport(section:HTMLElement,api:Api,onSaved:()=>Promise<void>):void{
  const panel=document.createElement('details');panel.className='trivia-import';
  panel.innerHTML=`<summary>Nhập câu hỏi từ Excel</summary><p>Điền sheet <strong>CauHoi</strong>, mỗi dòng một câu, 2–3 đáp án A–C. Tối đa 500 câu/file, 2 MB. Câu trùng bỏ qua; câu mới lưu Nháp. File mẫu cũ cần để trống D, E, F.</p><div class="actions"><a class="trivia-template" href="/assets/trivia-question-template.xlsx" download="Mau-cau-hoi-766.xlsx">Tải Excel mẫu</a><label>Chọn file .xlsx<input data-trivia-import-file type="file" accept=".xlsx"></label><button type="button" data-trivia-import-check>Kiểm tra file</button><button type="button" class="primary" data-trivia-import-save disabled>Lưu câu hỏi mới</button></div><p data-trivia-import-status role="status"></p><div data-trivia-import-report></div>`;
  section.querySelector('.trivia-bank-filters')!.before(panel);
  const file=panel.querySelector<HTMLInputElement>('[data-trivia-import-file]')!,check=panel.querySelector<HTMLButtonElement>('[data-trivia-import-check]')!,save=panel.querySelector<HTMLButtonElement>('[data-trivia-import-save]')!;
  const status=panel.querySelector<HTMLElement>('[data-trivia-import-status]')!,preview=panel.querySelector<HTMLElement>('[data-trivia-import-report]')!;
  let encoded='',busy=false;
  file.addEventListener('change',()=>{encoded='';save.disabled=true;preview.innerHTML='';status.textContent='';});
  async function execute(confirm:boolean){if(busy)return;busy=true;check.disabled=save.disabled=file.disabled=true;
    try{
      if(!confirm){const selected=file.files?.[0];if(!selected||!selected.name.toLowerCase().endsWith('.xlsx'))throw new Error('Hãy chọn file Excel .xlsx theo mẫu.');if(selected.size>2*1024*1024)throw new Error('File Excel tối đa 2 MB.');encoded=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]??'');reader.onerror=()=>reject(new Error('Không đọc được file.'));reader.readAsDataURL(selected);});}
      if(!encoded)throw new Error('Hãy kiểm tra file trước khi lưu.');
      status.textContent=confirm?'Đang lưu câu hỏi…':'Đang kiểm tra file…';
      const report=await api<Report>('admin/trivia/import',{file:encoded,confirm});preview.innerHTML=importReport(report);
      if(confirm){encoded='';status.textContent=`Đã lưu ${report.saved} câu ở trạng thái Nháp. Bỏ qua ${report.duplicates.length} câu trùng.`;await onSaved();}
      else{save.disabled=!report.valid||report.newCount===0;status.textContent=report.valid?'Kiểm tra xong. Bấm Lưu câu hỏi mới để xác nhận.':'File có lỗi. Chưa lưu câu hỏi; sửa các dòng lỗi rồi chọn lại file.';}
    }catch(error){encoded='';save.disabled=true;status.textContent=(error as Error).message;}
    finally{busy=false;check.disabled=file.disabled=false;}
  }
  check.addEventListener('click',()=>void execute(false));save.addEventListener('click',()=>void execute(true));
}
