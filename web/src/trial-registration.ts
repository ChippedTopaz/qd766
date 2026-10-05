import {loginView} from './login-view.js';
import type TomSelectControl from 'tom-select';
declare const TomSelect: typeof TomSelectControl;
type Status={state:'draft'|'pending'|'approved'|'rejected';name:string;email:string;csrfToken:string};
type Directory={provinces:Array<{id:string;name:string}>;units:Array<{id:string;name:string}>};

export async function mountTrialRegistration(root:HTMLElement,local:boolean):Promise<boolean>{
  const response=await fetch('/api/v1/auth/registration',{cache:'no-store'});
  if(!response.ok)return false;
  let profile=await response.json() as Status;
  if(profile.state==='approved')return false;
  root.innerHTML=loginView({pending:true,name:profile.name,local,googleEnabled:true});
  const form=root.querySelector<HTMLElement>('.login-form')!;
  form.classList.add('registration-panel');
  const logout=async()=>{await fetch('/api/v1/auth/logout',{method:'POST',headers:{'X-QD766-CSRF':profile.csrfToken}});location.assign('/');};
  if(profile.state==='draft'){
    form.innerHTML='<h2 id="login-title">Đăng ký dùng thử</h2><p class="login-description">Chọn tỉnh và cơ quan công tác.</p><form data-registration><label>Tỉnh/thành phố<select data-province required></select></label><label>Cơ quan, đơn vị<select data-unit required></select></label><p class="login-foot">Phạm vi sử dụng: cơ quan được phê duyệt.</p><p data-message role="status"></p><button type="submit" class="btn primary">Gửi đăng ký</button></form><button type="button" class="text-button" data-logout>Đổi tài khoản</button>';
    const directoryResponse=await fetch('/api/v1/auth/registration/directory',{cache:'no-store'});
    if(!directoryResponse.ok)throw new Error('Chưa tải được danh sách tỉnh/cơ quan. Vui lòng thử lại.');
    const directory=await directoryResponse.json() as Directory;
    const province=form.querySelector<HTMLSelectElement>('[data-province]')!;
    const unit=form.querySelector<HTMLSelectElement>('[data-unit]')!;
    const submit=form.querySelector<HTMLButtonElement>('[type=submit]')!;
    const message=form.querySelector<HTMLElement>('[data-message]')!;
    for(const item of directory.provinces){const option=new Option(item.name,item.id);province.add(option);}
    const units=new TomSelect(unit,{placeholder:'Tìm cơ quan, đơn vị…',maxItems:1,create:false});
    let loading=0;
    const loadUnits=async()=>{
      const version=++loading;submit.disabled=true;units.disable();units.clear();units.clearOptions();message.textContent='';
      try{
        const reply=await fetch(`/api/v1/auth/registration/directory?provinceId=${encodeURIComponent(province.value)}`,{cache:'no-store'});
        if(!reply.ok)throw new Error('Chưa tải được danh sách cơ quan.');
        const data=await reply.json() as Directory;if(version!==loading)return;
        units.addOptions(data.units.map(item=>({value:item.id,text:item.name})));units.enable();
        if(!data.units.length)message.textContent='Tỉnh này chưa có danh sách cơ quan.';
      }catch(error){if(version===loading)message.textContent=error instanceof Error?error.message:'Không thể tải danh sách.';}
      finally{if(version===loading)submit.disabled=false;}
    };
    const provinces=new TomSelect(province,{placeholder:'Tìm tỉnh/thành phố…',maxItems:1,create:false,onChange:()=>void loadUnits()});
    await loadUnits();
    form.querySelector('form')!.addEventListener('submit',async event=>{
      event.preventDefault();submit.disabled=true;message.textContent='';
      try{
        const reply=await fetch('/api/v1/auth/registration',{method:'POST',headers:{'Content-Type':'application/json','X-QD766-CSRF':profile.csrfToken},body:JSON.stringify({provinceId:province.value,unitId:unit.value})});
        const body=await reply.json();if(!reply.ok)throw new Error(typeof body.detail==='string'?body.detail:'Không thể gửi đăng ký.');
        provinces.destroy();units.destroy();profile.state='pending';waiting();
      }catch(error){message.textContent=error instanceof Error?error.message:'Không thể gửi đăng ký.';submit.disabled=false;}
    });
    form.querySelector('[data-logout]')!.addEventListener('click',()=>void logout());
  }else waiting();
  function waiting(){
    form.innerHTML='<h2 id="login-title" data-heading></h2><p class="login-description" data-description></p><p data-message role="status"></p><button class="btn primary" data-check>Kiểm tra trạng thái</button><a class="login-google" href="/" data-enter hidden>Vào hệ thống</a><button type="button" class="text-button" data-logout>Đổi tài khoản</button>';
    const display=()=>{
      form.querySelector('[data-heading]')!.textContent=profile.state==='approved'?'Đăng ký đã được duyệt':profile.state==='rejected'?'Đăng ký chưa được phê duyệt':'Đang chờ phê duyệt';
      form.querySelector('[data-description]')!.textContent=profile.state==='approved'?'Tài khoản đã sẵn sàng sử dụng.':profile.state==='rejected'?'Vui lòng liên hệ quản trị viên.':'Bạn có thể quay lại bằng tài khoản Google đã đăng ký.';
      (form.querySelector('[data-enter]') as HTMLElement).hidden=profile.state!=='approved';
      (form.querySelector('[data-check]') as HTMLElement).hidden=profile.state==='approved';
    };
    const check=async()=>{
      const button=form.querySelector<HTMLButtonElement>('[data-check]')!;button.disabled=true;
      try{const reply=await fetch('/api/v1/auth/registration',{cache:'no-store'});if(!reply.ok)throw new Error('Phiên đã hết hạn. Vui lòng đăng nhập lại.');profile=await reply.json() as Status;display();form.querySelector('[data-message]')!.textContent='';}
      catch(error){form.querySelector('[data-message]')!.textContent=error instanceof Error?error.message:'Chưa kiểm tra được trạng thái.';}
      finally{button.disabled=false;}
    };
    form.querySelector('[data-check]')!.addEventListener('click',()=>void check());
    form.querySelector('[data-logout]')!.addEventListener('click',()=>void logout());
    display();
    const poll=()=>window.setTimeout(async()=>{if(!form.isConnected||profile.state!=='pending')return;if(!document.hidden)await check();poll();},15000);poll();
  }
  return true;
}
