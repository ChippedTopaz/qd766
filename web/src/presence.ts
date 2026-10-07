let online:number|null=null,started=false,busy=false;
let timer:number|undefined,failures=0,nextAttempt=0;
const label=()=>online===null?'—':new Intl.NumberFormat('vi-VN').format(online);

export function presenceBadge():string{
  return `<span class="online-indicator" title="Tài khoản có hoạt động trong 3 phút gần đây. Mỗi tài khoản tính một lần; số liệu gần thời gian thực." style="display:inline-flex;align-items:center;gap:7px;font-size:12px;white-space:nowrap;padding:7px 10px;border-radius:20px;background:#ecfdf5;color:#047857"><span aria-hidden="true">●</span>Đang online: <strong data-online-count>${label()}</strong></span>`;
}

function update(){document.querySelectorAll<HTMLElement>('[data-online-count]').forEach(node=>{node.textContent=label()})}

export function startPresence():void{
  if(started)return;started=true;
  const poll=async()=>{
    if(busy)return;
    window.clearTimeout(timer);
    if(document.hidden){timer=window.setTimeout(()=>void poll(),60000);return}
    if(Date.now()<nextAttempt){timer=window.setTimeout(()=>void poll(),nextAttempt-Date.now());return}
    busy=true;
    const controller=new AbortController();const timeout=window.setTimeout(()=>controller.abort(),8000);
    try{
      const response=await fetch('/api/v1/presence',{cache:'no-store',signal:controller.signal});
      if(!response.ok)throw new Error('Presence unavailable');
      const body=await response.json() as {onlineUsers:number};
      if(!Number.isSafeInteger(body.onlineUsers)||body.onlineUsers<0)throw new Error('Invalid presence');
      online=body.onlineUsers;failures=0;
    }catch{online=null;failures=Math.min(failures+1,3)}
    finally{
      window.clearTimeout(timeout);busy=false;update();
      const delay=Math.min(300000,60000*2**failures);nextAttempt=Date.now()+delay;
      timer=window.setTimeout(()=>void poll(),delay);
    }
  };
  document.addEventListener?.('visibilitychange',()=>{if(!document.hidden)void poll()});
  void poll();
}
