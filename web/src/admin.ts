import {installTrialCreditManager} from "./trial-credit-admin.js";
import {accountPageQuery,accountPageSummary,accountPager} from "./admin-account-filters.js";
import {installAdminLayout} from "./admin-layout.js";
import {installSystemNoticeAdmin} from './admin-system-notices.js';
import {installTriviaBank} from './admin-trivia.js';
import {presenceBadge,startPresence} from './presence.js';
import {installAnalysisConfiguration} from "./admin-analysis-configuration.js";
import {installFormulaConfiguration} from './admin-formula-configuration.js';
import {installLogHub} from "./admin-log-hub.js";
import {installAdminAudit} from "./admin-audit-log.js";
import {installRegistrationAdmin} from "./admin-registration.js";
import {adminSubscriptionCell,type SubscriptionSummary} from "./admin-subscription.js";
import {installSourceMonitor} from './admin-source-monitor.js';
import {ServiceError,serviceStateFor,readServiceJson,userFacingError,renderServiceState,bindServiceRetry} from './service-feedback.js';
let layout:ReturnType<typeof installAdminLayout>|null=null;
let creditManager:Awaited<ReturnType<typeof installTrialCreditManager>>=null;
type Account={id:string;email:string|null;name:string;role:string;admitted:boolean;active:boolean;accessTier:string;provinceId:string|null;unitId:string|null;provinceName?:string|null;unitName?:string|null;credits:number;reservedCredits:number;subscription?:SubscriptionSummary|null;canActivateTrial?:boolean};
type Directory={provinces:{id:string;name:string}[];units:{id:string;name:string}[]};
const root=document.querySelector<HTMLElement>("#admin")!;
const esc=(v:unknown)=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]!));
let csrf="",accounts:Account[]=[],directory:Directory={provinces:[],units:[]},editing:string|null=null;
type AccountPage={items:Account[];page:number;pageSize:number;total:number;totalAll:number;units:{id:string;name:string}[]};
let accountPage=1,accountTotal=0,accountTotalAll=0,accountUnits:{id:string;name:string}[]=[],accountRead=0,searchTimer:ReturnType<typeof setTimeout>|undefined;
function acceptAccountPage(result:AccountPage){accounts=result.items;accountPage=result.page;accountTotal=result.total;accountTotalAll=result.totalAll;accountUnits=result.units;}
const activationTokens=new Map<string,string>();
const get=<T extends HTMLElement>(id:string)=>document.getElementById(id) as T;
const pendingReads=new Map<string,Promise<unknown>>();
async function api<T>(path:string,body?:unknown):Promise<T>{
  if(body!==undefined)return request<T>(path,body);
  const pending=pendingReads.get(path);if(pending)return pending as Promise<T>;
  const promise=request<T>(path).finally(()=>pendingReads.delete(path));pendingReads.set(path,promise);return promise;
}
async function request<T>(path:string,body?:unknown):Promise<T>{
  let response:Response;
  try{response=await fetch(`/api/v1/${path}`,body===undefined?{cache:"no-store"}:{method:"POST",headers:{"Content-Type":"application/json","X-QD766-CSRF":csrf},body:JSON.stringify(body)});}catch(error){throw new ServiceError(serviceStateFor(error));}
  return readServiceJson<T>(response);
}
function message(value:string){get("message").textContent=value;}
async function run(action:()=>Promise<void>){try{await action();}catch(error){message(userFacingError(error));}}
function options(items:{id:string;name:string}[]){return items.map(i=>`<option value="${esc(i.id)}">${esc(i.name)}</option>`).join("");}
async function loadUnits(unit?:string|null){const province=get<HTMLSelectElement>('province').value;if(!province){get('unit').innerHTML='<option value="">Chọn tỉnh/thành phố trước</option>';return;}directory=await api<Directory>(`admin/directory?provinceId=${encodeURIComponent(province)}`);get("unit").innerHTML=options(directory.units);if(unit)get<HTMLSelectElement>("unit").value=unit;}
function toggleTier(){const agency=get<HTMLSelectElement>("tier").value==="agency";get("unit-label").hidden=!agency;get<HTMLSelectElement>('unit').required=agency;get<HTMLSelectElement>('unit').disabled=!agency;}
function assignment(){const accessTier=get<HTMLSelectElement>("tier").value;return {provinceId:get<HTMLSelectElement>("province").value,accessTier,unitId:accessTier==="agency"?get<HTMLSelectElement>("unit").value:null};}
function filterUnits(){
  const province=get<HTMLSelectElement>("account-province").value;
  const select=get<HTMLSelectElement>("account-unit"),selected=select.value;
  const units=accountUnits;
  select.innerHTML='<option value="">Tất cả cơ quan</option>'+options(units);
  select.disabled=!province;if(units.some(u=>u.id===selected))select.value=selected;
}
function showAccounts(){
  filterUnits();
  const formatter=new Intl.NumberFormat("vi-VN"),num=(value:number)=>formatter.format(value);
  get('account-count').textContent=accountPageSummary(accountPage,accountTotal,accountTotalAll);
  get('accounts-pagination').innerHTML=accountPager(accountPage,accountTotal);
  get("accounts").innerHTML=accounts.map(a=>`<tr>
    <td>${esc(a.name)}<br><small>${esc(a.email)}</small></td>
    <td>${a.role==="admin"?"Quản trị":a.accessTier==="national"?"Toàn quốc":a.accessTier==="agency"?"Cơ quan":"Cả tỉnh"}</td>
    <td>${esc(a.provinceName??directory.provinces.find(p=>p.id===a.provinceId)?.name??"Chưa gán")}</td>
    <td>${esc(a.accessTier==="agency"?(a.unitName??"Chưa gán cơ quan"):a.role==="admin"||a.accessTier==="national"?"Toàn quốc":"Toàn tỉnh")}</td>
    <td><span class="pill">${!a.active?"Đã khóa":a.admitted?"Được mời":"Chưa được mời"}</span></td>
    <td>${adminSubscriptionCell(a.subscription)}</td>
    <td style="font-variant-numeric:tabular-nums;text-align:right"><strong>${num(a.credits)}</strong><small style="display:block">Đang giữ ${num(a.reservedCredits)}</small>${a.subscription?`<small style="display:block">Subscription ${num(a.subscription.subscriptionCredits)} · Mua riêng ${num(a.subscription.purchasedCredits)}</small>`:""}</td>
    <td><div class="account-actions">${creditManager&&a.active&&a.admitted?`<button data-add-credit="${esc(a.id)}">Thêm Credit</button>`:""}${a.role!=="admin"?`<button data-edit="${a.id}">Phân quyền / khóa</button>`:""}${a.canActivateTrial?`<button data-activate-trial="${a.id}" title="Bắt đầu 1 tháng miễn phí và cấp 100 Credit subscription">Kích hoạt dùng thử</button>`:""}</div></td></tr>`).join("")||'<tr><td colspan="8">Không có tài khoản phù hợp.</td></tr>';
}
async function loadAccountPage(page=accountPage){
  const sequence=++accountRead;
  const query=accountPageQuery(page,get<HTMLInputElement>('search').value,get<HTMLSelectElement>('account-province').value,get<HTMLSelectElement>('account-unit').value,get<HTMLSelectElement>('account-status').value);
  get('account-count').textContent='Đang tải tài khoản…';
  get('accounts-pagination').querySelectorAll<HTMLButtonElement>('button').forEach(b=>b.disabled=true);
  try{const result=await api<AccountPage>('admin/accounts?'+query);if(sequence!==accountRead)return;acceptAccountPage(result);showAccounts();}
  catch(error){if(sequence!==accountRead)return;get('account-count').textContent='Chưa tải được danh sách tài khoản.';get('accounts').innerHTML='<tr><td colspan="8">Không thể tải danh sách. Vui lòng thử lại.</td></tr>';get('accounts-pagination').innerHTML='<button type="button" data-account-page="'+page+'">Thử lại</button>';throw error;}
}
async function refresh(){await loadAccountPage();}
async function start(){try{
  const me=await api<{role:string;csrfToken:string;name:string}>("auth/me");if(me.role!=="admin")throw new Error("Chỉ tài khoản quản trị được truy cập.");csrf=me.csrfToken;
  const initial=await Promise.all([api<Directory>("admin/directory"),api<AccountPage>("admin/accounts?page=1"),api("access-policy")]);
  directory=initial[0];acceptAccountPage(initial[1]);
  const initialApi:typeof api=<T>(path:string,body?:unknown):Promise<T>=>path==="access-policy"&&body===undefined?Promise.resolve(initial[2] as T):api<T>(path,body);
root.innerHTML=`<header><div><h1>Quản trị hệ thống</h1><p>${esc(me.name)} · Quản lý tài khoản và phân quyền QĐ766</p></div><a class="button" href="/">Về Tổng quan</a></header><p id="message" role="status"></p>
<section data-account-editor="true" hidden><h2 id="form-title">Phân quyền tài khoản</h2><form id="form"><div class="form-grid"><label>Tỉnh/thành phố<select id="province" required>${options(directory.provinces)}</select></label><label>Phạm vi xem<select id="tier"><option value="national">Toàn quốc (không có quyền quản trị)</option><option value="province">Cả tỉnh và cơ quan thuộc tỉnh</option><option value="agency">Chỉ cơ quan được gán</option></select></label><label id="unit-label" hidden>Cơ quan<select id="unit"></select></label><label id="active-label">Trạng thái<select id="active"><option value="true">Đang hoạt động</option><option value="false">Khóa tài khoản</option></select></label></div><div class="actions"><button id="save" class="primary">Lưu quyền</button><button id="cancel" type="button">Hủy chỉnh sửa</button></div></form></section>
<section data-account-list="true"><h2>Tài khoản</h2><input id="search" placeholder="Tìm tên hoặc email…" aria-label="Tìm tài khoản"><div class="scroll"><table><thead><tr><th>Người dùng</th><th>Quyền</th><th>Tỉnh</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody id="accounts"></tbody></table></div></section>
<section data-legacy-audit="true"><h2>Nhật ký quản trị</h2><div class="scroll"><table><thead><tr><th>Hành động</th><th>Thời điểm</th></tr></thead><tbody id="audit"></tbody></table></div></section>`;
  const accountHeader=get("accounts").closest("table")?.querySelector("thead tr");
  root.querySelector('header')?.insertAdjacentHTML('beforeend',presenceBadge());startPresence();
  accountHeader?.closest("table")?.classList.add("admin-accounts-table");
  if(accountHeader){const th=document.createElement("th");th.textContent="Cơ quan";accountHeader.insertBefore(th,accountHeader.children[3]!);}
  const filters=document.createElement("div");filters.className="account-filters";
  get("search").before(filters);filters.append(get("search"));
  filters.insertAdjacentHTML("beforeend",`<label>Tỉnh/thành phố<select id="account-province"><option value="">Tất cả tỉnh/thành phố</option>${options(directory.provinces)}</select></label><label>Cơ quan<select id="account-unit" disabled><option value="">Tất cả cơ quan</option></select></label>`);
  filters.insertAdjacentHTML('beforeend','<label>Trạng thái tài khoản<select id="account-status"><option value="">Tất cả trạng thái</option><option value="active">Đang hoạt động</option><option value="unadmitted">Chưa được mời</option><option value="locked">Đã khóa</option></select></label>');
  filters.insertAdjacentHTML('afterend','<p id="account-count" class="account-count" role="status"></p>');
  get('accounts').closest('.scroll')?.insertAdjacentHTML('afterend','<nav id="accounts-pagination" class="account-pagination" aria-label="Phân trang tài khoản"></nav>');
  get("account-province").addEventListener("change",()=>{get<HTMLSelectElement>("account-unit").value="";accountUnits=[];filterUnits();clearTimeout(searchTimer);void run(()=>loadAccountPage(1));});
  for(const id of ['account-unit','account-status'])get(id).addEventListener('change',()=>{clearTimeout(searchTimer);void run(()=>loadAccountPage(1));});
  root.addEventListener('click',event=>{const button=(event.target as HTMLElement).closest<HTMLButtonElement>('[data-account-page]');if(button&&!button.disabled)void run(()=>loadAccountPage(Number(button.dataset.accountPage)));});
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
  filterUnits();showAccounts();installLogHub(root,api,directory.provinces);installAdminAudit(root,api);installAnalysisConfiguration(root,api);installFormulaConfiguration(root,api);installTriviaBank(root,api);installSourceMonitor(root,api);installSystemNoticeAdmin(root,api);layout=installAdminLayout(root);
  // Agency choices are loaded only when editing an existing account.
  get("unit").innerHTML='<option value="">Chọn cơ quan</option>';
  get("tier").addEventListener("change",()=>{if(get<HTMLSelectElement>("tier").value==="agency"&&!get<HTMLSelectElement>("unit").value)void run(()=>loadUnits());});
  get("tier").addEventListener("change",toggleTier);get("province").addEventListener("change",()=>void run(()=>loadUnits()));get<HTMLInputElement>('search').maxLength=200;get("search").addEventListener("input",()=>{++accountRead;clearTimeout(searchTimer);searchTimer=setTimeout(()=>void run(()=>loadAccountPage(1)),250);});
  get("cancel").addEventListener("click",()=>{editing=null;layout?.closeEdit();});
  get("form").addEventListener("submit",event=>{event.preventDefault();void run(async()=>{if(!editing)throw new Error('Vui lòng chọn tài khoản cần điều chỉnh.');const button=get<HTMLButtonElement>("save");if(button.disabled)return;button.disabled=true;try{await api(`admin/accounts/${editing}`,{...assignment(),active:get<HTMLSelectElement>("active").value==="true"});message("Đã lưu quyền; phiên cũ đã được thu hồi. Người dùng cần đăng nhập lại.");editing=null;layout?.closeEdit();await refresh();}finally{button.disabled=false;}});});
  root.addEventListener("click",event=>{const button=(event.target as HTMLElement).closest<HTMLButtonElement>("button");if(button?.dataset.edit){void run(async()=>{const a=accounts.find(a=>a.id===button.dataset.edit)!;editing=a.id;layout?.edit();get<HTMLSelectElement>("province").value=a.provinceId??"";get<HTMLSelectElement>("tier").value=a.accessTier;get<HTMLSelectElement>("active").value=String(a.active);const save=get<HTMLButtonElement>('save');save.disabled=true;try{await loadUnits(a.unitId);toggleTier();get("form-title").textContent=`Phân quyền: ${a.name}`;get("form").scrollIntoView({behavior:"smooth"});}catch(error){editing=null;layout?.closeEdit();throw error;}finally{save.disabled=false;}});}});
}catch(error){console.error('Admin page could not load',error);root.innerHTML=renderServiceState(error,{admin:true});bindServiceRetry(root);}finally{root.setAttribute("aria-busy","false");}}
void start();
