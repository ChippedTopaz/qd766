import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {filterAdminAccounts,accountUnitOptions} from '../dist/admin-account-filters.js';
const accounts=[
 {id:'a',name:'An',email:'an@example.test',provinceId:'pt',provinceName:'Phú Thọ',unitId:'x1',unitName:'UBND xã Một'},
 {id:'b',name:'Bình',email:null,provinceId:'pt',provinceName:'Phú Thọ',unitId:'x2',unitName:'UBND xã Hai'},
 {id:'c',name:'C',email:null,provinceId:'na',provinceName:'Nghệ An',unitId:'x3',unitName:'UBND xã Một'},
 {id:'d',name:'D',email:null,provinceId:'pt',provinceName:'Phú Thọ',unitId:'x1',unitName:'UBND xã Một'},
];
assert.equal(filterAdminAccounts(accounts,'','','').length,4);
assert.deepEqual(filterAdminAccounts(accounts,'','pt','x2').map(a=>a.id),['b']);
assert.deepEqual(filterAdminAccounts(accounts,'nghệ an','','').map(a=>a.id),['c']);
assert.deepEqual(filterAdminAccounts(accounts,'xã một','pt','').map(a=>a.id),['a','d']);
assert.deepEqual(filterAdminAccounts(accounts,'AN@EXAMPLE.TEST','','').map(a=>a.id),['a']);
assert.equal(filterAdminAccounts(accounts,'','na','x1').length,0);
assert.deepEqual(accountUnitOptions(accounts,'pt').map(a=>a.id).sort(),['x1','x2']);
const html=readFileSync(new URL('../admin.html',import.meta.url),'utf8');
assert.equal((html.match(/<body>/g)||[]).length,1);
assert.match(html,/id="admin-startup"[\s\S]*admin-sidebar/);
const css=readFileSync(new URL('../admin.css',import.meta.url),'utf8');
assert.match(css,/#admin\[aria-busy="true"\]\{display:none\}/);
assert.match(css,/aria-busy="false".*#admin-startup/);
const source=readFileSync(new URL('../src/admin.ts',import.meta.url),'utf8');
assert.match(source,/data-add-credit/);assert.match(source,/openAccount\(button.dataset.addCredit/);
console.log('ADMIN_ACCOUNT_FILTERS_OK: province/unit/search, unique scoped units, initial sidebar and credit shortcut');
