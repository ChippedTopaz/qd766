import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const app=readFileSync(new URL('../dist/app.js',import.meta.url),'utf8');
const navBody=app.slice(app.indexOf('function nav()'),app.indexOf('function baseNav()'));
const base='<aside><nav><button data-nav="overview">Tổng quan</button><button data-nav="time">Thời gian</button><button data-nav="peers" class="">Cơ quan</button><button data-nav="formulas">Công thức</button></nav></aside>';
function render({publicMode=true,paid=true,allowed=true,role='user',screen='overview'}={}){
 return new Function('baseNav','signedInUser','accountMenu','triviaMarkup','publicReadOnly','paidRequestsEnabled','canAcquire','state','icon',
  navBody+';return nav();')(()=>base,{role},()=>'',()=>'',publicMode,paid,()=>allowed,{screen},()=>'<svg></svg>');
}
for(const role of ['admin','user']){
 const html=render({role,screen:'procedure'});
 assert.match(html,/<span>Tra cứu theo TTHC<\/span>/);
 assert.equal((html.match(/data-nav="procedure"/g)||[]).length,1);
 assert(html.indexOf('data-nav="peers"')<html.indexOf('data-nav="procedure"'));
 assert(html.indexOf('data-nav="procedure"')<html.indexOf('data-nav="formulas"'));
 assert.match(html,/data-nav="procedure" class="active"/);
 assert.equal(html.includes('data-action="open-admin"'),role==='admin');
}
for(const options of [{allowed:false},{paid:false},{publicMode:false}]){
 assert.doesNotMatch(render(options),/data-nav="procedure"/);
}
assert.match(app,/id: "procedure", label: "Tra cứu theo TTHC"/);
console.log('PROCEDURE_SIDEBAR_PASS: label, placement, active state and permission gates unchanged');
