import assert from 'node:assert/strict';
import {pendingRegistrationRow} from '../dist/admin-registration.js';
const row=pendingRegistrationRow({id:'test',name:'Nguyễn Văn A',email:'a@example.com',province:'Phú Thọ',unit:'UBND xã',provinceId:'root',unitId:'unit',birthDate:'1990-05-17',gender:'male',workplace:'Văn phòng UBND'});
assert.equal((row.match(/<td>/g)||[]).length,10);
for(const text of ['<strong>Nguyễn Văn A</strong>','17/05/1990','Nam','a@example.com','Văn phòng UBND'])assert.ok(row.includes(text));
assert.ok(!pendingRegistrationRow({id:'test',name:'<img src=x onerror=alert(1)>',email:'a@example.com',province:'Phú Thọ',unit:'UBND xã',provinceId:'root',unitId:'unit'}).includes('<img'));
console.log('ADMIN_REGISTRATION_ROW_OK');
