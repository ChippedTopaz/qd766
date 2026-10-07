import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const {importReport}=await import(new URL('../dist/admin-trivia-import.js',import.meta.url));
const html=importReport({valid:false,newCount:1,saved:0,errors:[{row:4,message:'<script>bad</script>'}],duplicates:[{row:3,prompt:'<img src=x>'}],questions:[{row:2,prompt:'Câu hỏi <b>',choices:['Có','Không'],correctIndex:1,explanation:'<img>'}]});
assert.match(html,/Dòng 4/);assert.match(html,/&lt;script&gt;/);assert.match(html,/&lt;img/);assert(!html.includes('<script>'));assert.match(html,/>B<\/td>/);
const src=await readFile(new URL('../src/admin-trivia-import.ts',import.meta.url),'utf8');
assert.match(src,/confirm\}/);assert.match(src,/2\*1024\*1024/);assert.match(src,/report\.valid\|\|report\.newCount===0/);assert.match(src,/save\.disabled=true/);assert(!/window\.confirm|alert\(/.test(src));
console.log('TRIVIA_IMPORT_UI_TEST_OK');
