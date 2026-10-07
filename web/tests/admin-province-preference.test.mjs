import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {lastAdminProvince,rememberAdminProvince,clearAdminProvince} from '../dist/admin-province-preference.js';
const values=new Map(),store={getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};
const admin={id:'admin-one',role:'admin'},other={id:'admin-two',role:'admin'};
const a='019d2be3-6a88-732b-8b17-b68020c8553a',b='019d2be3-6a81-771b-b671-9078297c4a7b';
assert.equal(lastAdminProvince(admin,store),null);
rememberAdminProvince(admin,a,store);assert.equal(lastAdminProvince(admin,store),a);
rememberAdminProvince(admin,b,store);assert.equal(lastAdminProvince(admin,store),b);
assert.equal(lastAdminProvince(other,store),null);
for(const role of ['user','province','agency']){
  const user={...admin,role};assert.equal(lastAdminProvince(user,store),null);
  rememberAdminProvince(user,a,store);assert.equal(lastAdminProvince(admin,store),b);
}
rememberAdminProvince(admin,'not-a-province',store);assert.equal(lastAdminProvince(admin,store),b);
const blocked={getItem(){throw Error('blocked')},setItem(){throw Error('blocked')},removeItem(){throw Error('blocked')}};
assert.equal(lastAdminProvince(admin,blocked),null);rememberAdminProvince(admin,a,blocked);clearAdminProvince(admin,blocked);
clearAdminProvince(admin,store);assert.equal(lastAdminProvince(admin,store),null);
assert.equal(lastAdminProvince({role:'admin'},store),null);
const src=readFileSync(new URL('../src/app.ts',import.meta.url),'utf8');
assert.match(src,/explicitProvince\|\|lastAdminProvince\(signedInUser\)/);
assert.match(src,/rememberedProvince&&!explicitProvince&&\[403,404,422\]\.includes\(apiResponse.status\)/);
assert.equal((src.match(/rememberAdminProvince\(signedInUser,data.province.id\)/g)||[]).length,2);
console.log('ADMIN_PROVINCE_PREFERENCE_OK: per-account, admin-only, last successful province, explicit URL priority, stale fallback, blocked storage safe');
