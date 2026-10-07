import {installTrialCreditManager} from "./trial-credit-admin.js";
import {filterAdminAccounts,accountUnitOptions} from "./admin-account-filters.js";
import {installAdminLayout} from "./admin-layout.js";
import {presenceBadge,startPresence} from './presence.js';
import {installAnalysisConfiguration} from "./admin-analysis-configuration.js";
import {installCollectionMonitor} from "./admin-collection.js";
import {installRegistrationAdmin} from "./admin-registration.js";
import {adminSubscriptionCell,type SubscriptionSummary} from "./admin-subscription.js";
let layout:ReturnType<typeof installAdminLayout>|null=null;
let creditManager:Awaited<ReturnType<typeof installTrialCreditManager>>=null;
type Account={id:string;email:string|null;name:string;role:string;admitted:boolean;active:boolean;accessTier:string;provinceId:string|null;unitId:string|null;provinceName?:string|null;unitName?:string|null;credits:number;reservedCredits:number;subscription?:SubscriptionSummary|null;canActivateTrial?:boolean};
type Directory={provinces:{id:string;name:string}[];units:{id:string;name:string}[]};
type Invitation={id:string;email:string|null;state:string;expiresAt:string};
const root=document.querySelector<HTMLElement>("#admin")!;
const esc=(v:unknown)=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]!));
let csrf="",accounts:Account[]=[],directory:Directory={provinces:[],units:[]},editing:string|null=null;
const activationTokens=new Map<string,string>();
const get=<T extends HTMLElement>(id:string)=>document.getElementById(id) as T;
const pendingReads=new Map<string,Promise<unknown>>();
async function api<T>(path:string,body?:unknown):Promise<T>{
  if(body!==undefined)return request<T>(path,body);
  const pending=pendingReads.get(path);if(pending)return pending as Promise<T>;
  const promise=request<T>(path).finally(()=>pendingReads.delete(path));pendingReads.set(path,promise);return promise;
}
async function request<T>(path:string,body?:unknown):Promise<T>{
  const response=await fetch(`/api/v1/${path}`,body===undefined?{cache:"no-store"}:{method:"POST",headers:{"Content-Type":"application/json","X-QD766-CSRF":csrf},body:JSON.stringify(body)});
  const value=await response.json();if(!response.ok)throw new Error(typeof value.detail==="string"?value.detail:"Không thực hiện được yêu cầu.");return value as T;
}
function message(value:string){get("message").textContent=value;}
async function run(action:()=>Promise<void>){try{await action();}catch(error){message(error instanceof Error?error.message:String(error));}}
function options(items:{id:string;name:string}[]){return items.map(i=>`<option value="${esc(i.id)}">${esc(i.name)}</option>`).join("");}
async function loadUnits(unit?:string|null){directory=await api<Directory>(`admin/directory?provinceId=${encodeURIComponent(get<HTMLSelectElement>("province").value)}`);get("unit").innerHTML=options(directory.units);if(unit)get<HTMLSelectElement>("unit").value=unit;}
function toggleTier(){get("unit-label").hidden=get<HTMLSelectElement>("tier").value!=="agency";}
function assignment(){const accessTier=get<HTMLSelectElement>("tier").value;return {provinceId:get<HTMLSelectElement>("province").value,accessTier,unitId:accessTier==="agency"?get<HTMLSelectElement>("unit").value:null};}
function filterUnits(){
  const province=get<HTMLSelectElement>("account-province").value;
  const select=get<HTMLSelectElement>("account-unit"),selected=select.value;
  const units=accountUnitOptions(accounts,province);
  select.innerHTML='<option value="">Tất cả cơ quan</option>'+options(units);
  select.disabled=!province;if(units.some(u=>u.id===selected))select.value=selected;
}
function showAccounts(){
  filterUnits();
  const search=get<HTMLInputElement>("search").value.toLocaleLowerCase("vi");
  const formatter=new Intl.NumberFormat("vi-VN"),num=(value:number)=>formatter.format(value);
  const province=get<HTMLSelectElement>("account-province").value,unit=get<HTMLSelectElement>("account-unit").value;
  get("accounts").innerHTML=filterAdminAccounts(accounts,search,province,unit).map(a=>`<tr>
    <td>${esc(a.name)}<br><small>${esc(a.email)}</small></td>
    <td>${a.role==="admin"?"Quản trị":a.accessTier==="national"?"Toàn quốc":a.accessTier==="agency"?"Cơ quan":"Cả tỉnh"}</td>
    <td>${esc(a.provinceName??directory.provinces.find(p=>p.id===a.provinceId)?.name??"Chưa gán")}</td>
    <td>${esc(a.accessTier==="agency"?(a.unitName??"Chưa gán cơ quan"):a.role==="admin"||a.accessTier==="national"?"Toàn quốc":"Toàn tỉnh")}</td>
    <td><span class="pill">${!a.active?"Đã khóa":a.admitted?"Được mời":"Chưa được mời"}</span></td>
    <td>${adminSubscriptionCell(a.subscription)}</td>
    <td style="font-variant-numeric:tabular-nums;text-align:right"><strong>${num(a.credits)}</strong><small style="display:block">Đang giữ ${num(a.reservedCredits)}</small>${a.subscription?`<small style="display:block">Subscription ${num(a.subscription.subscriptionCredits)} · Mua riêng ${num(a.subscription.purchasedCredits)}</small>`:""}</td>
    <td><div class="account-actions">${creditManager&&a.active&&a.admitted?`<button data-add-credit="${esc(a.id)}">Thêm Credit</button>`:""}${a.role!=="admin"?`<button data-edit="${a.id}">Phân quyền / khóa</button>`:""}${a.canActivateTrial?`<button data-activate-trial="${a.id}" title="Bắt đầu 1 tháng miễn phí và cấp 100 Credit subscription">Kích hoạt dùng thử</button>`:""}</div></td></tr>`).join("")||'<tr><td colspan="8">Không có tài khoản phù hợp.</td></tr>';
}
async function loadInvitations(){const invitations=await api<Invitation[]>("admin/invitations");const labels:Record<string,string>={available:"Chưa dùng",used:"Đã dùng",expired:"Hết hạn",revoked:"Đã thu hồi"};get("invitations").innerHTML=invitations.map(i=>`<tr><td>${esc(i.email??"Người có link")}</td><td>${esc(labels[i.state])}</td><td>${new Date(i.expiresAt).toLocaleString("vi-VN")}</td><td>${i.state==="available"?`<button data-revoke="${i.id}">Thu hồi</button>`:""}</td></tr>`).join("");}
async function loadAudit(){const audit=await api<{action:string;at:string}[]>("admin/audit");get("audit").innerHTML=audit.map(a=>`<tr><td>${esc(a.action)}</td><td>${new Date(a.at).toLocaleString("vi-VN")}</td></tr>`).join("");}
async function refresh(){accounts=await api<Account[]>("admin/accounts");showAccounts();await Promise.all([loadInvitations(),loadAudit()]);}
async function start(){try{
  const me=await api<{role:string;csrfToken:string;name:string}>("auth/me");if(me.role!=="admin")throw new Error("Chỉ tài khoản quản trị được truy cập.");csrf=me.csrfToken;
  const initial=await Promise.all([api<Directory>("admin/directory"),api<Account[]>("admin/accounts"),api("access-policy")]);
  directory=initial[0];accounts=initial[1];
  const initialApi:typeof api=<T>(path:string,body?:unknown):Promise<T>=>path==="access-policy"&&body===undefined?Promise.resolve(initial[2] as T):api<T>(path,body);
  root.innerHTML=`<header><div><h1>Quản trị dùng thử</h1><p>${esc(me.name)} · Lời mời và phân quyền QĐ766</p></div><a class="button" href="/">Về Tổng quan</a></header><p id="message" role="status"></p><section><h2 id="form-title">Tạo lời mời</h2><p>Link dùng một lần. Nên gắn email để chỉ đúng người được mời có thể sử dụng. Không có email: người có link có thể nhận quyền.</p><form id="form"><div class="form-grid"><label>Tỉnh/thành phố<select id="province" required>${options(directory.provinces)}</select></label><label>Phạm vi xem<select id="tier"><option value="national">Toàn quốc (không có quyền quản trị)</option><option value="province">Cả tỉnh và cơ quan thuộc tỉnh</option><option value="agency">Chỉ cơ quan được gán</option></select></label><label id="unit-label" hidden>Cơ quan<select id="unit"></select></label><label id="email-label">Email người được mời (tùy chọn)<input id="email" type="email" maxlength="320"></label><label id="days-label">Hạn lời mời (ngày)<input id="days" type="number" min="1" max="30" value="7" required></label><label id="active-label" hidden>Trạng thái<select id="active"><option value="true">Đang hoạt động</option><option value="false">Khóa tài khoản</option></select></label></div><div class="actions"><button id="save" class="primary">Tạo link mời</button><button id="cancel" type="button" hidden>Hủy chỉnh sửa</button></div></form><p id="invite-result"></p></section><section><h2>Tài khoản</h2><input id="search" placeholder="Tìm tên hoặc email…" aria-label="Tìm tài khoản"><div class="scroll"><table><thead><tr><th>Người dùng</th><th>Quyền</th><th>Tỉnh</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody id="accounts"></tbody></table></div></section><section><h2>Lời mời đã tạo</h2><div class="scroll"><table><thead><tr><th>Người nhận</th><th>Trạng thái</th><th>Hết hạn</th><th>Thao tác</th></tr></thead><tbody id="invitations"></tbody></table></div></section><section><h2>Nhật ký quản trị</h2><div class="scroll"><table><thead><tr><th>Hành động</th><th>Thời điểm</th></tr></thead><tbody id="audit"></tbody></table></div></section>`;
  const accountHeader=get("accounts").closest("table")?.querySelector("thead tr");
  root.querySelector('header')?.insertAdjacentHTML('beforeend',presenceBadge());startPresence();
  accountHeader?.closest("table")?.classList.add("admin-accounts-table");
  if(accountHeader){const th=document.createElement("th");th.textContent="Cơ quan";accountHeader.insertBefore(th,accountHeader.children[3]!);}
  const filters=document.createElement("div");filters.className="account-filters";
  get("search").before(filters);filters.append(get("search"));
  filters.insertAdjacentHTML("beforeend",`<label>Tỉnh/thành phố<select id="account-province"><option value="">Tất cả tỉnh/thành phố</option>${options(directory.provinces)}</select></label><label>Cơ quan<select id="account-unit" disabled><option value="">Tất cả cơ quan</option></select></label>`);
  get("account-province").addEventListener("change",()=>{get<HTMLSelectElement>("account-unit").value="";filterUnits();showAccounts();});
  get("account-unit").addEventListener("change",showAccounts);
  root.addEventListener("click",event=>{const button=(event.target as HTMLElement).closest<HTMLButtonElement>("[data-add-credit]");if(!button||!creditManager)return;button.disabled=true;void run(async()=>{try{await creditManager!.openAccount(button.dataset.addCredit!);layout?.credits();const input=get<HTMLInputElement>("credit-amount");input.focus();input.select();}finally{button.disabled=false;}});});
  if(accountHeader){for(const title of ["Subscription","Credit"]){const th=document.createElement("th");th.textContent=title;accountHeader.insertBefore(th,accountHeader.lastElementChild);}}
  root.addEventListener("click",event=>{
    const button=(event.target as HTMLElement).closest<HTMLButtonElement>("[data-activate-trial]");
    const id=button?.dataset.activateTrial;if(!button||!id)return;
    if(!activationTokens.has(id))activationTokens.set(id,crypto.randomUUID());
    button.disabled=true;
    void run(async()=>{try{
      await api(`admin/accounts/${id}/trial-activation`,{operationId:activationTokens.get(id)});
      activationTokens.delete(id);message("Đã kích hoạt 1 tháng miễn phí và cấp 100 Credit subscription. Quyền xem và quyền khai thác giữ nguyên.");
      await refresh();
    }finally{button.disabled=false;}});
  });
  await Promise.all([
    installTrialCreditManager(root,initialApi,refresh,true).then(manager=>{creditManager=manager;}),
    installRegistrationAdmin(root,initialApi,async()=>{await refresh();filterUnits();},true)
  ]);
  filterUnits();showAccounts();installCollectionMonitor(root,api);installAnalysisConfiguration(root,api);layout=installAdminLayout(root);
  root.addEventListener("click",event=>{const key=(event.target as HTMLElement).closest<HTMLElement>("[data-admin-section]")?.dataset.adminSection;if(key==="invitations")void run(loadInvitations);if(key==="audit")void run(loadAudit);});
  // Agency choices belong to the invitation form, not the initial account screen.
  get("unit").innerHTML='<option value="">Chọn cơ quan</option>';
  get("tier").addEventListener("change",()=>{if(get<HTMLSelectElement>("tier").value==="agency"&&!get<HTMLSelectElement>("unit").value)void run(()=>loadUnits());});
  get("tier").addEventListener("change",toggleTier);get("province").addEventListener("change",()=>void run(()=>loadUnits()));get("search").addEventListener("input",showAccounts);
  get("cancel").addEventListener("click",()=>{editing=null;layout?.invite();get("form-title").textContent="Tạo lời mời";get("save").textContent="Tạo link mời";get("cancel").hidden=true;get("active-label").hidden=true;get("email-label").hidden=false;get("days-label").hidden=false;});
  get("form").addEventListener("submit",event=>{event.preventDefault();void run(async()=>{const button=get<HTMLButtonElement>("save");button.disabled=true;try{if(editing){await api(`admin/accounts/${editing}`,{...assignment(),active:get<HTMLSelectElement>("active").value==="true"});message("Đã lưu quyền; phiên cũ đã được thu hồi. Người dùng cần đăng nhập lại.");}else{const invite=await api<{token:string}>("admin/invitations",{...assignment(),email:get<HTMLInputElement>("email").value||null,days:Number(get<HTMLInputElement>("days").value)});const link=`${location.origin}/#invite=${invite.token}`;get("invite-result").innerHTML=`<strong>Link chỉ hiển thị lần này:</strong> <a href="${esc(link)}">${esc(link)}</a> <button id="copy" type="button">Sao chép</button>`;get("copy").addEventListener("click",()=>void run(async()=>{await navigator.clipboard.writeText(link);message("Đã sao chép link mời.");}));message("Đã tạo lời mời. Chỉ gửi riêng cho người cần dùng thử.");}await refresh();}finally{button.disabled=false;}});});
  root.addEventListener("click",event=>{const button=(event.target as HTMLElement).closest<HTMLButtonElement>("button");if(button?.dataset.edit){void run(async()=>{const a=accounts.find(a=>a.id===button.dataset.edit)!;editing=a.id;layout?.edit();get<HTMLSelectElement>("province").value=a.provinceId??"";get<HTMLSelectElement>("tier").value=a.accessTier;get<HTMLSelectElement>("active").value=String(a.active);await loadUnits(a.unitId);toggleTier();get("form-title").textContent=`Phân quyền: ${a.name}`;get("save").textContent="Lưu quyền";get("cancel").hidden=false;get("active-label").hidden=false;get("email-label").hidden=true;get("days-label").hidden=true;get("invite-result").textContent="";get("form").scrollIntoView({behavior:"smooth"});});}if(button?.dataset.revoke)void run(async()=>{await api(`admin/invitations/${button.dataset.revoke}/revoke`,{});message("Đã thu hồi lời mời.");await refresh();});});
}catch(error){root.innerHTML=`<section><h1>Không thể mở quản trị</h1><p>${esc(error instanceof Error?error.message:error)}</p><a class="button" href="/">Về trang chủ</a></section>`;}finally{root.setAttribute("aria-busy","false");}}
void start();
