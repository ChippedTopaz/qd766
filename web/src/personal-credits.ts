import {renderSourceWallet,sourceLabel,type SourceWallet} from "./source-wallet-ui.js";
type Entry={type:string;source?:string;amount:number;availableDelta:number;reservedDelta:number;availableAfter:number;reservedAfter:number;at:string};
type Wallet=SourceWallet&{availableCredits:number;reservedCredits:number;total:number;items:Entry[]};
const num=(n:number)=>new Intl.NumberFormat("vi-VN").format(n);
const esc=(v:string)=>v.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]!));
export function requestCreditDisplay(state:string,cost:number|null):string{
  if(cost===null)return "Quản trị";
  if(state==="ready"||state==="succeeded")return `<span style="color:#dc2626;font-variant-numeric:tabular-nums">-${num(cost)}</span>`;
  return `<span style="font-variant-numeric:tabular-nums" ${["waiting","reserved","queued","running"].includes(state)?`title="Đang giữ ${num(cost)} credit; chưa ghi nhận thu"`:""}>0</span>`;
}
export function openPersonalCredits(onBalance?:(available:number,reserved:number)=>void):void{
  const previous=document.activeElement as HTMLElement|null;
  const dialog=document.createElement("dialog");
  dialog.setAttribute("aria-label","Credit của tôi");
  dialog.style.cssText="width:min(920px,94vw);max-height:90vh;border:1px solid #e2e8f0;border-radius:24px;padding:24px;color:#0f172a;background:white;box-shadow:0 20px 80px #0f172a20;overflow:auto";
  let offset=0;
  let redemptionToken:string|null=null;
  document.body.append(dialog);
  dialog.addEventListener("close",()=>{dialog.remove();previous?.focus();});
  dialog.showModal();
  async function load(){
    dialog.innerHTML='<p role="status">Đang tải credit…</p>';
    try{
      const response=await fetch(`/api/v1/me/credits?offset=${offset}&limit=25`,{cache:"no-store"});
      if(!response.ok)throw new Error("Không thể tải lịch sử credit. Vui lòng thử lại.");
      const data=await response.json() as Wallet;
      if(!dialog.isConnected)return;
      const labels:Record<string,string>={topup:"Cấp / nạp thêm Credit",grant:"Cấp Credit",reserve:"Giữ Credit",charge:"Thu Credit",release:"Hoàn Credit",refund:"Hoàn Credit",expire:"Hết hạn",redemption:"Đổi Credit gia hạn",adjustment:"Điều chỉnh"};
      dialog.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center"><h2>Credit của tôi</h2><button class="btn" data-close>Đóng</button></div><div style="display:flex;gap:16px;flex-wrap:wrap;margin:20px 0"><div class="panel" style="padding:20px;flex:1"><span>Credit khả dụng</span><h2 style="font-variant-numeric:tabular-nums">${num(data.availableCredits)}</h2></div><div class="panel" style="padding:20px;flex:1"><span>Credit đang giữ</span><h2 style="font-variant-numeric:tabular-nums">${num(data.reservedCredits)}</h2></div></div><p class="muted">Credit đang giữ chưa phải chi phí đã thu. Yêu cầu thất bại được hoàn toàn bộ. Chưa hỗ trợ nạp tiền trực tuyến.</p><h3>Lịch sử giao dịch</h3><div class="table-wrap" style="overflow:auto"><table style="width:100%;min-width:620px;font-variant-numeric:tabular-nums"><thead><tr><th>Thời gian</th><th>Giao dịch</th><th style="text-align:right">Credit</th><th style="text-align:right">Khả dụng sau giao dịch</th><th style="text-align:right">Đang giữ</th></tr></thead><tbody>${data.items.map(row=>{
        const delta=row.type==="charge"||row.type==="redemption"?-row.amount:row.availableDelta;
        const display=row.type==="reserve"?`Giữ ${num(row.amount)}`:`${delta>0?"+":""}${num(delta)}`;
        return `<tr><td>${esc(new Date(row.at).toLocaleString("vi-VN"))}</td><td>${esc(labels[row.type]??"Giao dịch")}</td><td style="text-align:right;color:${row.type==="charge"?"#dc2626":delta>0?"#15803d":"#64748b"}">${display}</td><td style="text-align:right">${num(row.availableAfter)}</td><td style="text-align:right">${num(row.reservedAfter)}</td></tr>`;
      }).join("")||'<tr><td colspan="5">Chưa có giao dịch.</td></tr>'}</tbody></table></div><div style="display:flex;justify-content:space-between;gap:12px;margin-top:16px"><button class="btn" data-prev ${offset===0?"disabled":""}>Trang trước</button><span>${num(data.total)} giao dịch</span><button class="btn" data-next ${offset+25>=data.total?"disabled":""}>Trang sau</button></div>`;
      dialog.querySelector("h3")?.insertAdjacentHTML("beforebegin",renderSourceWallet(data));
      const tableWrap=dialog.querySelector<HTMLElement>(".table-wrap");if(tableWrap)tableWrap.style.maxHeight="360px";
      if(data.walletMode==="sources"){
        const heading=document.createElement("th");heading.textContent="Nguồn";
        dialog.querySelector("thead tr")?.insertBefore(heading,dialog.querySelector("thead tr")?.children[2]??null);
        dialog.querySelectorAll("tbody tr").forEach((tr,index)=>{
          if(!data.items[index]){tr.querySelector("td")?.setAttribute("colspan","6");return;}
          const cell=document.createElement("td");cell.textContent=sourceLabel(data.items[index].source);
          tr.insertBefore(cell,tr.children[2]??null);
        });
      }
      dialog.querySelectorAll<HTMLElement>("thead th").forEach(th=>{th.style.position="sticky";th.style.top="0";th.style.background="#f8fafc";th.style.zIndex="1";});
      const renewConfirm=dialog.querySelector<HTMLElement>("[data-renew-confirm]");
      dialog.querySelector("[data-renew]")?.addEventListener("click",()=>{if(renewConfirm)renewConfirm.hidden=false;});
      dialog.querySelector("[data-cancel-renew]")?.addEventListener("click",()=>{if(renewConfirm)renewConfirm.hidden=true;});
      dialog.querySelector<HTMLButtonElement>("[data-confirm-renew]")?.addEventListener("click",async event=>{
        const button=event.currentTarget as HTMLButtonElement;button.disabled=true;
        const status=dialog.querySelector<HTMLElement>("[data-renew-status]");
        try{
          const me=await fetch("/api/v1/auth/me",{cache:"no-store"});
          if(!me.ok)throw new Error("Phiên đăng nhập đã hết hạn.");
          const profile=await me.json() as {csrfToken:string};
          redemptionToken??=crypto.randomUUID();
          const response=await fetch("/api/v1/me/subscription/redemption",{method:"POST",headers:{"Content-Type":"application/json","X-QD766-CSRF":profile.csrfToken},body:JSON.stringify({token:redemptionToken,expectedCost:data.redemptionCost})});
          const result=await response.json() as {detail?:string;availableCredits:number};
          if(!response.ok)throw new Error(result.detail??"Không thể gia hạn. Vui lòng thử lại.");
          redemptionToken=null;
          onBalance?.(result.availableCredits,data.reservedCredits);
          await load();
          const done=dialog.querySelector<HTMLElement>("[data-renew-status]");if(done)done.textContent="Gia hạn thành công.";
        }catch(error){if(status)status.textContent=error instanceof Error?error.message:"Không thể gia hạn.";button.disabled=false;}
      });
      dialog.querySelector("[data-prev]")?.addEventListener("click",()=>{offset=Math.max(0,offset-25);void load();});
      dialog.querySelector("[data-next]")?.addEventListener("click",()=>{offset+=25;void load();});
    }catch(error){if(dialog.isConnected)dialog.innerHTML=`<p role="alert">${esc(error instanceof Error?error.message:"Không thể tải credit.")}</p><button class="btn" data-retry>Thử lại</button><button class="btn" data-close>Đóng</button>`;dialog.querySelector("[data-retry]")?.addEventListener("click",()=>void load());}
    dialog.querySelector("[data-close]")?.addEventListener("click",()=>dialog.close());
  }
  void load();
}
