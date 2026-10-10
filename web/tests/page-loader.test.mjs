import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pageLoader} from '../dist/page-loader.js';
const read=name=>readFileSync(new URL('../'+name,import.meta.url),'utf8');
const markup=pageLoader();
assert.match(markup,/role="status"/);
assert.match(markup,/aria-hidden="true"/);
assert.match(markup,/Đang tải dữ liệu/);
for(const name of ['index.html','admin.html']){
  const html=read(name);
  assert.match(html,/aria-busy="true"/);
  assert.match(html,name==='admin.html'?/id="admin-startup"[\s\S]*page-loader/:/page-loader-full/);
  assert.match(html,/<noscript>/);
  assert.doesNotMatch(html,/boot-side/);
}
const block=css=>css.slice(css.indexOf('/* QD766 page loader:'),css.indexOf('/* End QD766 page loader. */'));
assert.equal(block(read('bento.css')),block(read('admin.css')));
assert.match(block(read('bento.css')),/prefers-reduced-motion:reduce/);
assert.match(block(read('bento.css')),/100dvh/);
assert.doesNotMatch(block(read('bento.css')),/position:fixed|z-index/);
assert.match(read('src/app.ts'),/kind === "loading"\) return pageLoader\(\)/);

// Deferred startup failure: spinner stays during the request, then gives way to
// the normal error screen and clears busy state, on both application surfaces.
for(const [module,id,title] of [['app','app','Không thể tải dữ liệu'],['admin','admin','Không thể mở quản trị']]){
  const root={innerHTML:markup,attrs:{'aria-busy':'true'},setAttribute(k,v){this.attrs[k]=v;}};
  globalThis.document={querySelector(selector){return selector==='#'+id?root:null;}};
  globalThis.location={pathname:'/',search:'',hash:''};
  let rejectFetch;
  globalThis.fetch=()=>new Promise((_,reject)=>{rejectFetch=reject;});
  await import('../dist/'+module+'.js?loader-test');
  assert.match(root.innerHTML,/page-loader/);
  assert.equal(root.attrs['aria-busy'],'true');
  rejectFetch(new Error('Test connection error'));
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.match(root.innerHTML,new RegExp(title));
  assert.doesNotMatch(root.innerHTML,/page-loader/);
  assert.equal(root.attrs['aria-busy'],'false');
}
// Login is an early return, not an error: it must also replace the loader.
const loginRoot={innerHTML:markup,attrs:{'aria-busy':'true'},setAttribute(k,v){this.attrs[k]=v;}};
globalThis.document={querySelector(selector){return selector==='#app'?loginRoot:null;},querySelectorAll(){return [];}};
globalThis.fetch=async url=>url==='/api/v1/access-policy'
  ?{ok:true,json:async()=>({publicReadOnly:true,loginRequired:true,googleLoginEnabled:true})}
  :{ok:false,status:401,json:async()=>({})};
await import('../dist/app.js?loader-login');
await new Promise(resolve=>setTimeout(resolve,0));
assert.match(loginRoot.innerHTML,/Đăng nhập với Google/);
assert.doesNotMatch(loginRoot.innerHTML,/page-loader|Không thể tải dữ liệu/);
assert.equal(loginRoot.attrs['aria-busy'],'false');
console.log('PAGE_LOADER_OK: initial HTML, inline loading, matching styles, reduced motion, login and failure cleanup');
