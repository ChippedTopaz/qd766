import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {ServiceError,serviceCopy,serviceStateFor,userFacingError,readServiceJson,renderServiceState,bindServiceRetry} from '../dist/service-feedback.js';
for(const text of ['Failed to fetch',"Unexpected token 'I', Internal Server Error",'NetworkError when attempting to fetch resource','Illegal invocation','Website chưa kết nối được backend HTTPS máy cơ quan.','SQLAlchemy sqlite Error','HTTP 502']){
 const friendly=userFacingError(new Error(text));assert.equal(friendly,serviceCopy.unavailable.message);assert.doesNotMatch(renderServiceState(new Error(text)),/backend HTTPS|Internal Server|SQLAlchemy|Failed to fetch|HTTP 502/);
}
for(const text of ['Bạn còn 2 Credit, cần 5 Credit để thực hiện.','Kỳ báo cáo chưa có dữ liệu.','Tên người đăng ký không hợp lệ.','Không ghi nhận thu Credit.'])assert.equal(userFacingError(new Error(text)),text,'Business and financial messages retained');
const validation=renderServiceState(new Error('Link đăng ký đã hết hạn.'));
assert.match(validation,/Link đăng ký đã hết hạn/);assert.match(validation,/Chưa thể hoàn tất yêu cầu/);
assert.doesNotMatch(renderServiceState(new Error('<script>alert(1)</script>')),/<script>/);
assert.equal(serviceStateFor(new DOMException('slow','TimeoutError')),'slow');assert.equal(userFacingError(new DOMException('slow','TimeoutError')),serviceCopy.slow.message);
for(const kind of Object.keys(serviceCopy)){
 const html=renderServiceState(new ServiceError(kind),{admin:true});
 assert.match(html,new RegExp(serviceCopy[kind].title));assert.match(html,/viewBox="0 0 300 230"/);assert.match(html,/aria-hidden="true"/);assert.match(html,/role="status"/);
 assert.doesNotMatch(html,/https:\/\//,'No external image/font/service request');
 if(kind==='session'){assert.match(html,/Đăng nhập lại/);assert.doesNotMatch(html,/data-service-retry/);}else assert.match(html,/data-service-retry/);
}
assert.match(renderServiceState('offline',{compact:true}),/service-state-compact/);
const successful=await readServiceJson(new Response(JSON.stringify({items:[1,2]})));assert.deepEqual(successful.items,[1,2]);
for(const status of [500,502,503])await assert.rejects(readServiceJson(new Response('<html>upstream</html>',{status})),e=>e instanceof ServiceError&&e.kind==='unavailable'&&e.status===status);
await assert.rejects(readServiceJson(new Response('<html>login</html>',{status:401})),e=>e.kind==='session');
await assert.rejects(readServiceJson(new Response('gateway html',{status:403})),e=>e.kind==='access');
await assert.rejects(readServiceJson(new Response(JSON.stringify({detail:'Xác nhận phiên không hợp lệ.'}),{status:403})),e=>e instanceof ServiceError&&e.kind==='refresh');
await assert.rejects(readServiceJson(new Response(JSON.stringify({detail:'Subscription đã hết hạn.'}),{status:403})),e=>!(e instanceof ServiceError)&&e.message==='Subscription đã hết hạn.');
assert.match(renderServiceState('refresh'),/Tải lại trang/);
assert.doesNotMatch(renderServiceState('refresh'),/data-service-login/);
assert.match(renderServiceState('session'),/Phiên làm việc đã kết thúc/);
await assert.rejects(readServiceJson(new Response('not json',{status:200})),e=>e.kind==='unavailable');
await assert.rejects(readServiceJson(new Response(JSON.stringify({detail:'Chọn cơ quan trước khi tiếp tục.'}),{status:422})),/Chọn cơ quan/);
await assert.rejects(readServiceJson(new Response(JSON.stringify({detail:'Không đủ Credit để thực hiện.'}),{status:409})),/Không đủ Credit/);
await assert.rejects(readServiceJson(new Response(JSON.stringify({detail:'<script>debug</script>'}),{status:403})),e=>e instanceof ServiceError);
const originalNavigator=Object.getOwnPropertyDescriptor(globalThis,'navigator');
Object.defineProperty(globalThis,'navigator',{value:{onLine:false},configurable:true});
assert.equal(serviceStateFor(new TypeError('Failed to fetch')),'offline');assert.equal(userFacingError(new TypeError('Failed to fetch')),serviceCopy.offline.message);
assert.equal(userFacingError(new Error('Chọn cơ quan trước khi tiếp tục.')),'Chọn cơ quan trước khi tiếp tục.');
if(originalNavigator)Object.defineProperty(globalThis,'navigator',originalNavigator);else delete globalThis.navigator;
let action,options,reloads=0;const button={disabled:false,textContent:'Thử lại',addEventListener(type,fn,opts){assert.equal(type,'click');action=fn;options=opts;}};
bindServiceRetry({querySelectorAll:()=>[button]},()=>reloads++);assert.equal(reloads,0,'No automatic retry');action();action();assert.equal(reloads,1);assert.equal(button.disabled,true);assert.deepEqual(options,{once:true});
const source=readFileSync(new URL('../src/service-feedback.ts',import.meta.url),'utf8');
assert.doesNotMatch(source,/\bfetch\s*\(|setInterval|setTimeout|method:\s*['"]POST/,'Feedback never sends or replays requests');
const app=readFileSync(new URL('../src/app.ts',import.meta.url),'utf8'),admin=readFileSync(new URL('../src/admin.ts',import.meta.url),'utf8');
assert.doesNotMatch(app,/backend HTTPS máy cơ quan|Hãy kiểm tra máy chủ cục bộ|Không dùng dữ liệu mẫu thay thế/);
assert.match(app,/productionSite&&policy.publicReadOnly!==true\)throw/,'Safe-public policy guard retained');
assert.match(app,/if\(publicReadOnly\|\|productionSite\)throw/,'Production cannot fall back to mock data');
assert.match(app,/root.innerHTML=renderServiceState\(error\)/);assert.match(admin,/renderServiceState\(error,\{admin:true\}\)/);
for(const name of ['personal-credits','trial-registration']){
 const module=readFileSync(new URL(`../src/${name}.ts`,import.meta.url),'utf8');
 assert.doesNotMatch(module,/if\(!\w+\.ok\)throw new Error\('Phiên/,'Non-auth HTTP failures must not imply session expiry');
 assert.match(module,/readServiceJson/);
}
console.log('SERVICE_FEEDBACK=PASS: 7 variants, HTTP 401 vs 403 CSRF vs 5xx, business validation preserved, offline, one manual retry, no requests/replay');
