export type SourceWallet={walletMode?:string;subscriptionCredits?:number;purchasedCredits?:number;
  legacyCredits?:number;subscriptionEndsAt?:string|null;creditExpirations?:{amount:number;at:string}[];
  subscriptionState?:"active"|"scheduled"|"expired"|"none";
  redemptionCost?:number|null;canRedeem?:boolean};
const num=(n:number)=>new Intl.NumberFormat("vi-VN").format(n);
export const walletDate=(value:string)=>new Date(value).toLocaleString("vi-VN",{timeZone:"Asia/Ho_Chi_Minh"});
const esc=(v:string)=>v.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]!));
export function sourceLabel(source?:string):string{
  return ({subscription:"Subscription",purchased:"Bổ sung",mixed:"Kết hợp"} as Record<string,string>)[source??""]??"Chuyển tiếp";
}
export function renderSourceWallet(data:SourceWallet):string{
  if(data.walletMode!=="sources")return "";
  const next=(data.creditExpirations??[]).filter(lot=>lot.amount>0).sort((a,b)=>Date.parse(a.at)-Date.parse(b.at))[0];
  return `<section class="personal-wallet-sources">
    <div class="personal-credit-grid">
      <div><span>Credit subscription</span><strong>${num(data.subscriptionCredits??0)}</strong><small>Theo chu kỳ sử dụng</small></div>
      <div><span>Credit bổ sung</span><strong>${num(data.purchasedCredits??0)}</strong><small>Cộng dồn, không hết hạn</small></div>
    </div><p>${data.subscriptionEndsAt?`Subscription đến ${esc(walletDate(data.subscriptionEndsAt))}`:data.subscriptionState==="expired"?'<span style="color:#b91c1c;background:#fef2f2;border-radius:999px;padding:4px 10px">Subscription đã hết hạn</span>':data.subscriptionState==="scheduled"?"Subscription chưa đến ngày bắt đầu":"Chưa có subscription đang hiệu lực"}</p>
    ${data.subscriptionState==="expired"?'<p class="muted">Dữ liệu đã khai thác vẫn khả dụng. Gia hạn để khai thác thêm.</p>':""}
    ${next?`<p class="muted">${num(next.amount)} Credit subscription hết hạn: ${esc(walletDate(next.at))}</p>`:""}
    ${(data.legacyCredits??0)>0?`<p class="muted">Credit chuyển tiếp: ${num(data.legacyCredits!)} (được giữ riêng).</p>`:""}
    ${data.redemptionCost?`<p>Sử dụng ${num(data.redemptionCost)} Credit bổ sung để gia hạn 1 tháng. Kỳ gia hạn này không cấp thêm Credit.</p><button class="btn" data-renew ${data.canRedeem?"":"disabled"}>Gia hạn bằng Credit</button>${!data.canRedeem?'<small class="personal-renew-note">Khả dụng khi subscription hết hạn và đủ Credit bổ sung.</small>':""}<div data-renew-confirm hidden class="personal-renew-confirm"><p>Xác nhận sử dụng ${num(data.redemptionCost)} Credit bổ sung để gia hạn 1 tháng?</p><button class="btn primary" data-confirm-renew>Xác nhận gia hạn</button> <button class="btn" data-cancel-renew>Hủy</button></div>`:""}
    <p data-renew-status role="status"></p>
  </section>`;
}
