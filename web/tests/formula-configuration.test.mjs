import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
import {defaultFormulaConfiguration,renderFormulaReference} from '../dist/formula-reference.js';
test('original content is preserved except the requested proportional-score expressions',async()=>{
 const original=readFileSync(new URL('./fixtures/formula-reference-before-editor.txt',import.meta.url),'utf8');
 const js=ts.transpileModule(original,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace(/from ['"]\.\/([^'"]+)['"]/g,(_,file)=>`from '${new URL('../dist/'+file,import.meta.url).href}'`);
 const baseline=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
 // Requested proportional-score expressions and removal of the duplicate component panel only.
 for(const g of defaultFormulaConfiguration().groups){
  if(g.id==='formality-online-payment-tree')continue; // Explicitly approved 2+2+6 update has its own regression tests.
  const html=renderFormulaReference(g.id).replace(/<div class="formula-score-equation" data-score-mode="linear"[\s\S]*?<\/div><p class="formula-symbols">[\s\S]*?<\/p>/g,'').replace(/<div class="formula-extra">[\s\S]*?<\/div><\/div>/g,'');
  const previous=baseline.renderFormulaReference(g.id).replace(/<details class="formula-accordion formula-accordion-components" open>[\s\S]*?<\/details>/g,'').replace(/<details class="formula-guide">[\s\S]*?<\/details>\s*/g,'').replace(/(<h1>Công thức tính Bộ chỉ số 766<\/h1>)<p>[\s\S]*?<\/p>/,'$1').replaceAll('Cách tính và nghiệp vụ','Nghiệp vụ và cách tính').replace(/<div class="formula-equation"><span>Tỷ lệ (?:toàn trình|một phần|trực tiếp|bưu chính)[\s\S]*?<\/div>/g,'');
  // 5.1 is newly visible on request, without altering any other saved reference text.
  assert.equal(html.replace(/<article class="formula-card" data-formula-id="5.1">[\s\S]*?<\/article>/g,''),previous);
 }
 assert.deepEqual(JSON.parse(readFileSync(new URL('../../src/qd766/backend/formula_seed.json',import.meta.url),'utf8')),defaultFormulaConfiguration());
});

test('supplementary equations render under the main equation and support four operators',()=>{
 const config=defaultFormulaConfiguration(),f=config.groups[0].items[0];
 for(const [operator,symbol] of [['add','+'],['subtract','−'],['multiply','×'],['divide','÷']]){
  f.extras=[{label:'Phụ <test>',numerator:'A',denominator:'B',operator,multiplier:''}];
  const html=renderFormulaReference('transparency',config),extra=html.match(/<div class="formula-extra">[\s\S]*?<\/div><\/div>/)[0];
  assert(html.indexOf('formula-extra')<html.indexOf('formula-accordions'));
  assert.match(extra,/Công thức phụ/);assert.match(extra,/Phụ &lt;test&gt;/);assert.doesNotMatch(extra,/100%/);
  if(operator==='divide')assert.match(extra,/formula-fraction/);else assert(extra.includes(`<b>${symbol}</b>`));
 }
 const old=defaultFormulaConfiguration();const html=renderFormulaReference('provide-online-tree',old);
 for(const extra of old.groups[2].items.flatMap(f=>f.extras)){
  assert(html.includes(extra.label));assert(html.includes(extra.numerator));assert(html.includes(extra.denominator));
 }
 assert.equal((html.match(/class="formula-extra"/g)||[]).length,4);
});
test('blank threshold uses proportional points; set threshold uses capped threshold formula',()=>{
 const config=defaultFormulaConfiguration(),f=config.groups[0].items[0];
 f.maximum=6;f.target=null;
 let html=renderFormulaReference('transparency',config);assert.match(html,/data-score-mode="linear"/);assert.doesNotMatch(html,/Ngưỡng đạt:/);
 f.target=80;html=renderFormulaReference('transparency',config);assert.match(html,/Ngưỡng đạt: 80%/);assert.match(html,/formula-score-cases/);
 f.maximum=null;f.target=null;html=renderFormulaReference('transparency',config);assert.match(html,/Chưa xác định/);
 const firstCard=html.split('data-formula-id="1.2"')[0];assert.doesNotMatch(firstCard,/formula-score-equation/);
});
test('saved fields render and text is escaped, unknown maximum is not zero',()=>{
 const config=defaultFormulaConfiguration();const f=config.groups[0].items[0];
 f.title='<script>alert(1)</script>';f.maximum=null;f.target=75;f.businessLines=['Nội dung mới'];f.numerator='Tử số mới';config.groups[0].name='<script>group</script>';config.source.version='<script>version</script>';
 const html=renderFormulaReference('transparency',config);
 assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);assert.match(html,/Chưa xác định/);assert.match(html,/Ngưỡng đạt: 75%/);assert.match(html,/Nội dung mới/);assert.match(html,/Tử số mới/);
});
