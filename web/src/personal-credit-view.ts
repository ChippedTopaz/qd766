import {renderSourceWallet,sourceLabel,walletDate,type SourceWallet} from './source-wallet-ui.js';
export type CreditEntry={type:string;source?:string;amount:number;availableDelta:number;reservedDelta:number;availableAfter:number;reservedAfter:number;at:string};
export type PersonalWallet=SourceWallet&{accessTier?:string;role?:string;availableCredits:number;reservedCredits:number;total:number;items:CreditEntry[]};
export const CREDIT_PAGE_SIZE=15;
const num=(n:number)=>n.toLocaleString('vi-VN');
const esc=(v:string)=>v.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function personalCreditMarkup(data:PersonalWallet|null,tab:'general'|'history',offset:number,loading=false,error=''):string{
 const tabs=`<div class="personal-credit-tabs" role="tablist" aria-label="Credit của tôi">${[['general','Thông tin chung'],['history','Lịch sử giao dịch']].map(([id,label])=>`<button type="button" class="${tab===id?'active':''}" role="tab" id="credit-tab-${id}" aria-selected="${tab===id}" aria-controls="credit-panel" data-credit-tab="${id}">${label}</button>`).join('')}</div>`;
 const shell=(content:string)=>`<div class="personal-credit-header"><h2>Credit của tôi</h2><button class="btn" data-close>Đóng</button></div>${tabs}<div id="credit-panel" role="tabpanel" aria-labelledby="credit-tab-${tab}">${content}</div>`;
 if(error)return shell(`<p role="alert">${esc(error)}</p><button class="btn" data-retry>Thử lại</button>`);
 if(!data)return shell('<p role="status">Đang tải Credit…</p>');
 if(tab==='general'){
  const type=data.role==='admin'?'Quản trị hệ thống':({national:'Toàn quốc',province:'Cấp tỉnh',agency:'Cơ quan'} as Record<string,string>)[data.accessTier??'']??'Thành viên';
  return shell(`<p class="personal-account-type">Loại tài khoản: <strong>${type}</strong></p><div class="personal-credit-grid"><div><span>Credit khả dụng</span><strong>${num(data.availableCredits)}</strong></div><div><span>Credit đang giữ</span><strong>${num(data.reservedCredits)}</strong></div></div>${renderSourceWallet(data)}<p class="personal-credit-note">Credit đang giữ dành cho yêu cầu chưa hoàn tất. Yêu cầu không thành công sẽ được hoàn Credit.</p>`);
 }
 const labels:Record<string,string>={topup:'Bổ sung Credit',grant:'Cấp Credit',reserve:'Giữ Credit',charge:'Sử dụng Credit',release:'Hoàn Credit',refund:'Hoàn Credit',expire:'Hết hạn',redemption:'Gia hạn',adjustment:'Điều chỉnh'};
 const sources=data.walletMode==='sources';
 const rows=data.items.slice(0,CREDIT_PAGE_SIZE).map(row=>{
  const delta=row.type==='charge'||row.type==='redemption'?-row.amount:row.availableDelta;
  const display=row.type==='reserve'?'Giữ '+num(row.amount):(delta>0?'+':'')+num(delta);
  return `<tr><td>${esc(walletDate(row.at))}</td><td>${esc(labels[row.type]??'Giao dịch')}</td>${sources?`<td>${sourceLabel(row.source)}</td>`:''}<td class="num ${delta<0?'negative':delta>0?'positive':''}">${display}</td><td class="num">${num(row.availableAfter)}</td><td class="num">${num(row.reservedAfter)}</td></tr>`;
 }).join('');
 const pages=Math.max(1,Math.ceil(data.total/CREDIT_PAGE_SIZE)),page=Math.floor(offset/CREDIT_PAGE_SIZE)+1;
 return shell(`<p class="personal-credit-count">${num(data.total)} giao dịch${loading?' · Đang tải…':''}</p><div class="table-wrap personal-credit-history"><table><thead><tr><th>Thời gian</th><th>Giao dịch</th>${sources?'<th>Nguồn</th>':''}<th class="num">Credit</th><th class="num">Khả dụng sau giao dịch</th><th class="num">Đang giữ</th></tr></thead><tbody>${rows||`<tr><td colspan="${sources?6:5}">Chưa có giao dịch.</td></tr>`}</tbody></table></div><nav class="personal-credit-pagination" aria-label="Phân trang giao dịch"><button class="btn" data-prev ${offset===0||loading?'disabled':''}>Trang trước</button><span>Trang ${page}/${pages}</span><button class="btn" data-next ${offset+CREDIT_PAGE_SIZE>=data.total||loading?'disabled':''}>Trang sau</button></nav>`);
}
