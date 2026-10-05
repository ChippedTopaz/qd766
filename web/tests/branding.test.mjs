import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pageLoader} from '../dist/page-loader.js';
import {loginView} from '../dist/login-view.js';
const read=name=>readFileSync(new URL('../'+name,import.meta.url),'utf8');
const title='Hệ thống phân tích Bộ chỉ số 766';
for(const file of ['index.html','admin.html']){
  const html=read(file);
  assert.match(html,new RegExp('<title>'+title+'</title>'));
  assert.match(html,/rel="icon" type="image\/png" href="\/assets\/logo-cchc.png"/);
  assert.equal((html.match(/<footer /g)||[]).length,1);
  assert.match(html,/HỆ THỐNG THEO DÕI CHỈ SỐ PHỤC VỤ NGƯỜI DÂN, DOANH NGHIỆP TRONG THỰC HIỆN TTHC/);
  assert.match(html,/href="https:\/\/dichvucong.gov.vn\/danh-gia-chat-luong-phuc-vu"/);
  assert.doesNotMatch(html,/Phú Thọ|dành cho xã, phường tỉnh/);
}
const html=read('index.html');
assert.match(html,/property="og:image" content="https:\/\/bochiso766.com\/assets\/logo-cchc.png"/);
assert.match(html,/property="og:description" content="[^"]*toàn quốc/);
assert.match(html,/name="twitter:image"/);
assert.match(pageLoader(),/<img[^>]*logo-cchc.png/);
assert.match(loginView(),/<img[^>]*logo-cchc.png/);
assert.doesNotMatch(loginView(),/login-mark">766/);
const app=read('src/app.ts');
assert.equal((app.match(/document.title="Hệ thống phân tích Bộ chỉ số 766"/g)||[]).length,2);
assert.doesNotMatch(app,/document.title=.*data.province/);
const logo=readFileSync(new URL('../assets/logo-cchc.png',import.meta.url));
assert.equal(logo.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
assert(logo.length>10000);
console.log('BRANDING_OK: shared logo, favicon, nationwide metadata, constant title and source footer');
