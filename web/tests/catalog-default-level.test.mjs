import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const app=readFileSync(new URL('../dist/app.js',import.meta.url),'utf8');
const body=app.slice(app.indexOf('function initializeCatalogLevel()'),app.indexOf('let catalogPreviewRequest'));
const data={province:{id:'root'},units:[
 {departmentId:'ward',departmentLevel:'COMMUNE',departmentType:'COMMUNE'},
 {departmentId:'department',departmentLevel:'PROVINCE',departmentType:'PROVINCIAL_DEPARTMENT'},
 {departmentId:'root',departmentLevel:'PROVINCE',departmentType:'PROVINCE'},
]};
function fixture(account){
 const preview={level:'',selectedId:'old',offset:100};
 const initialize=new Function('signedInUser','data','catalogPreview',
  'let catalogDefaultContext=null;'+body+';return initializeCatalogLevel;')(account,data,preview);
 initialize();
 return {preview,initialize};
}
for(const [unitId,expected] of [['ward','ward'],['department','province'],['root',''],['missing','']]){
 const {preview,initialize}=fixture({id:'user',accessTier:'agency',unitId});
 assert.equal(preview.level,expected);
 assert.equal(preview.selectedId,null);assert.equal(preview.offset,0);
 preview.level='';preview.offset=100;preview.selectedId='chosen';
 initialize();
 assert.deepEqual(preview,{level:'',offset:100,selectedId:'chosen'});
}
// Defaults follow assigned account scope, not the unit currently being viewed.
assert.equal(fixture({id:'user',accessTier:'province',unitId:'ward'}).preview.level,'');
assert.equal(fixture({id:'admin',accessTier:'national',unitId:null}).preview.level,'');
assert.equal(fixture(null).preview.level,'');
const catalog=app.slice(app.indexOf('function catalogReady()'),app.indexOf('function catalogReady()')+110);
assert.match(catalog,/initializeCatalogLevel\(\)/);
const loader=app.slice(app.indexOf('async function loadCatalogPreview()'),app.indexOf('async function loadCatalogPreview()')+140);
assert.match(loader,/initializeCatalogLevel\(\)/);
assert(!app.includes('Yêu cầu của tôi'));
assert(app.includes('Lịch sử tra cứu'));
console.log('CATALOG_DEFAULT_LEVEL_PASS: assigned commune/department/province, manual override preserved and history renamed');
