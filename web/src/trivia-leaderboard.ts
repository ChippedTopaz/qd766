type Player={rank:number;name:string;province:string;best:number;correctAnswers:number};
const esc=(value:unknown)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function leaderboardRows(players:Player[]):string{
  return players.slice(0,20).map(p=>`<tr><td class="num">${esc(p.rank)}</td><td>${esc(p.name)}</td><td>${esc(p.province)}</td><td class="num"><strong>${esc(p.best)}</strong></td><td class="num">${esc(p.correctAnswers)}</td></tr>`).join('');
}
export async function openTriviaLeaderboard():Promise<void>{
  if(document.querySelector('.trivia-leaderboard'))return;
  const trigger=document.activeElement as HTMLElement|null;
  const dialog=document.createElement('dialog');dialog.className='trivia-leaderboard';
  dialog.setAttribute('aria-label','Bảng xếp hạng Hỏi đáp');
  dialog.innerHTML='<div class="trivia-leaderboard-heading"><div><h2>Bảng xếp hạng Hỏi đáp</h2><p>Top 20 · Chuỗi đúng cao nhất</p></div><button type="button" class="btn" data-close>Đóng</button></div><div data-leaderboard-content role="status">Đang tải bảng xếp hạng…</div>';
  document.body.append(dialog);dialog.showModal();
  dialog.querySelector('[data-close]')?.addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{dialog.remove();if(trigger?.isConnected)trigger.focus()},{once:true});
  try{
    const response=await fetch('/api/v1/me/trivia/leaderboard',{cache:'no-store',signal:AbortSignal.timeout(15000)});
    const body=await response.json();if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'Chưa tải được bảng xếp hạng.');
    if(!Array.isArray(body.players))throw new Error('Dữ liệu bảng xếp hạng không hợp lệ.');
    if(!dialog.isConnected)return;
    const content=dialog.querySelector<HTMLElement>('[data-leaderboard-content]')!;
    content.innerHTML=body.players.length?`<div class="trivia-leaderboard-scroll"><table><thead><tr><th>Hạng</th><th>Tên tài khoản Google</th><th>Tỉnh công tác</th><th>Chuỗi cao nhất</th><th>Câu trả lời đúng</th></tr></thead><tbody>${leaderboardRows(body.players)}</tbody></table></div><p class="trivia-leaderboard-note">Tổng số lượt trả lời đúng qua các lần chơi. Đồng chuỗi: ưu tiên người có nhiều lượt đúng hơn.</p>`:'Chưa có người chơi có câu trả lời đúng.';
  }catch(error){if(dialog.isConnected)dialog.querySelector<HTMLElement>('[data-leaderboard-content]')!.textContent=(error as Error).name==='TimeoutError'?'Máy chủ phản hồi chậm. Vui lòng thử lại.':(error as Error).message;}
}
