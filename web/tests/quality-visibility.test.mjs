import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
for(const roleCase of ['admin','province','agency']){
  const data=JSON.parse(readFileSync(new URL('../data/snapshots.json',import.meta.url)));
  const own=data.units.find(unit=>unit.departmentLevel==='COMMUNE');
  data.defaultUnitId=roleCase==='agency'?own.departmentId:data.province.id;
  const app={innerHTML:'',setAttribute(){},querySelector(){return null},querySelectorAll(){return []}};
  const qualityNav={dataset:{nav:'quality'},handlers:{},addEventListener(k,cb){this.handlers[k]=cb;}};
  const qualityButton={handlers:{},addEventListener(k,cb){this.handlers[k]=cb;}};
  globalThis.document={title:'',querySelector:s=>s==='#app'?app:s==='[data-action=open-quality]'?qualityButton:null,querySelectorAll:s=>s==='[data-nav]'?[qualityNav]:[]};
  globalThis.TomSelect=class{on(){}destroy(){}};
  globalThis.window={setTimeout:(fn,delay)=>{const timer=setTimeout(fn,delay);timer.unref();return timer},clearTimeout};
  globalThis.location={search:'',hash:'',pathname:'/'};
  globalThis.history={state:null,replaceState(){}};
  globalThis.scrollTo=()=>{};
  globalThis.fetch=async url=>{
    let body=[];
    if(url==='/api/v1/access-policy')body={publicReadOnly:true,loginRequired:true,googleLoginEnabled:true};
    else if(url==='/api/v1/auth/me')body={name:'Visibility test',role:roleCase==='admin'?'admin':'user',accessTier:roleCase==='agency'?'agency':'province',provinceId:data.province.id,unitId:own.departmentId,csrfToken:'test',credits:100,canCollect:true};
    else if(url.startsWith('/api/v1/dashboard?'))body=data;
    else if(url.includes('/selection?'))body={snapshot:Object.values(data.snapshots).find(s=>s.scope==='all'),metadata:{detailsAvailable:true}};
    return {ok:true,status:200,json:async()=>structuredClone(body)};
  };
  await import('../dist/app.js?quality-role='+roleCase);
  for(let i=0;i<10;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.doesNotMatch(app.innerHTML,/Không thể tải dữ liệu/);
  assert.equal(app.innerHTML.includes('data-nav="quality"'),roleCase==='admin');
  assert.equal(app.innerHTML.includes('data-action="open-quality"'),roleCase==='admin');
  assert(app.innerHTML.includes('data-action="export"'));
  assert(app.innerHTML.includes('data-action="brief"'));
  assert(qualityNav.handlers.click&&qualityButton.handlers.click);
  if(roleCase!=='admin'){
    const before=app.innerHTML;
    qualityNav.handlers.click();qualityButton.handlers.click();
    assert.equal(app.innerHTML,before,'forged quality navigation must not open the screen');
  }
}
const css=readFileSync(new URL('../bento.css',import.meta.url),'utf8');
assert.match(css,/\.context-actions \.btn\[data-action="new-collection"\],\.context-actions \.btn\[data-action="export"\],\.context-actions \.btn\[data-action="brief"\]\{width:152px;flex:0 0 152px/);
console.log('QUALITY_VISIBILITY_OK: admin visible, province/agency hidden and navigation guarded; three equal-width actions');
