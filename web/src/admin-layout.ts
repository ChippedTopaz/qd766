export function installAdminLayout(root:HTMLElement):{edit:()=>void;invite:()=>void;credits:()=>void}{
  const sections=Array.from(root.querySelectorAll<HTMLElement>(":scope > section"));
  const form=sections[0]!,accounts=sections[1]!,invitations=sections[2]!,audit=sections[3]!,credits=sections.find(s=>s.querySelector("#credit-form")),collection=sections.find(s=>s.dataset.collectionMonitor==="true");
  const workspace=document.createElement("div");workspace.className="admin-workspace";
  const sidebar=document.createElement("aside");sidebar.className="admin-sidebar";
  const items:Array<[string,string]>=[["accounts","Quản lý tài khoản"],["credits","Quản lý credits"],["invitations","Mời dùng thử"],["collection","Nhật ký hệ thống"],["audit","Nhật ký quản trị"]];
  const registration=sections.find(s=>s.dataset.registrationReview==="true"),sharedLinks=sections.find(s=>s.dataset.sharedLinks==="true");
  const aiConfiguration=sections.find(s=>s.dataset.analysisConfiguration==='true');
  if(aiConfiguration)items.splice(3,0,['ai-configuration','Cấu hình phân tích AI']);
  const formulas=sections.find(s=>s.dataset.formulaConfiguration==='true');
  if(formulas)items.push(['formulas','Công thức tính']);
  const trivia=sections.find(s=>s.dataset.triviaBank==='true');
  if(trivia)items.push(['trivia','Hỏi đáp nhanh']);
  if(registration)items.splice(3,0,["registrations","Đăng ký chờ duyệt"]);
  sidebar.innerHTML=`<a class="admin-brand" href="/"><span class="admin-logo"><img class="cchc-logo" src="/assets/logo-cchc.png" alt="Cải cách hành chính" width="44" height="44"></span> <span>Quản trị</span></a><nav aria-label="Quản trị">${items.map(([key,label])=>`<button data-admin-section="${key}">${label}</button>`).join("")}</nav><a class="button admin-back" href="/">Về Tổng quan</a>`;
  const panels:Record<string,HTMLElement>={};
  items.forEach(([key])=>{const panel=document.createElement("div");panel.dataset.adminPanel=key;panel.hidden=true;panels[key]=panel;workspace.append(panel);});
  panels.accounts!.append(accounts);panels.invitations!.append(form,invitations);panels.audit!.append(audit);
  if(sharedLinks)panels.invitations!.append(sharedLinks);
  if(registration)panels.registrations!.append(registration);
  if(collection)panels.collection!.append(collection);
  const lookupRequests=sections.find(s=>s.dataset.collectionSource==='user');
  if(lookupRequests){
    panels.collection!.append(lookupRequests);lookupRequests.hidden=true;
    const submenus=document.createElement('nav');submenus.className='collection-submenus';submenus.setAttribute('aria-label','Nhật ký hệ thống');
    submenus.innerHTML='<button type="button" data-collection-tab="system" class="active" aria-pressed="true">Nhật ký hệ thống</button><button type="button" data-collection-tab="user" aria-pressed="false">Yêu cầu tra cứu</button>';
    panels.collection!.prepend(submenus);
    submenus.addEventListener('click',event=>{
      const button=(event.target as HTMLElement).closest<HTMLButtonElement>('[data-collection-tab]');if(!button)return;
      const mode=button.dataset.collectionTab;
      if(collection)collection.hidden=mode!=='system';lookupRequests.hidden=mode!=='user';
      submenus.querySelectorAll<HTMLButtonElement>('button').forEach(item=>{const active=item===button;item.classList.toggle('active',active);item.setAttribute('aria-pressed',String(active));});
    });
  }
  if(aiConfiguration)panels['ai-configuration']!.append(aiConfiguration);
  if(formulas)panels.formulas!.append(formulas);
  if(trivia)panels.trivia!.append(trivia);
  const inviteHeading=document.createElement("div");
  inviteHeading.className="actions";
  inviteHeading.innerHTML='<h2 style="margin-right:auto">Mời dùng thử</h2><button type="button" class="primary" data-new-invite>Tạo link mời</button>';
  panels.invitations!.prepend(inviteHeading);
  const resetInvitation=()=>{
    root.querySelector<HTMLButtonElement>("#cancel")?.click();
    panels.invitations!.insertBefore(form,invitations);
  };
  inviteHeading.querySelector("[data-new-invite]")?.addEventListener("click",()=>{
    resetInvitation();form.scrollIntoView({behavior:"smooth",block:"start"});
    form.querySelector<HTMLInputElement>("#email")?.focus({preventScroll:true});
  });
  if(credits)panels.credits!.append(credits);else panels.credits!.innerHTML="<section><h2>Quản lý credits</h2><p>Chức năng cấp credit chưa được mở ở môi trường này.</p></section>";
  const header=root.querySelector("header"),message=root.querySelector("#message");
  if(header)workspace.prepend(header);if(message)workspace.insertBefore(message,workspace.children[1]??null);
  root.append(sidebar,workspace);root.classList.add("admin-shell");
  const select=(key:string)=>{Object.entries(panels).forEach(([id,panel])=>panel.hidden=id!==key);sidebar.querySelectorAll<HTMLButtonElement>("button").forEach(button=>{const active=button.dataset.adminSection===key;button.classList.toggle("active",active);button.setAttribute("aria-current",active?"page":"false");});};
  sidebar.querySelectorAll<HTMLButtonElement>("button").forEach(button=>button.addEventListener("click",()=>{
    if(button.dataset.adminSection==="invitations")resetInvitation();
    select(button.dataset.adminSection!);
  }));
  select("accounts");
  return {credits:()=>select("credits"),edit:()=>{panels.accounts!.prepend(form);select("accounts");},invite:()=>{panels.invitations!.insertBefore(form,invitations);select("invitations");}};
}
