import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {triviaDeleteMarkup} from '../dist/admin-trivia-delete.js';
const html=triviaDeleteMarkup({id:'q',revision:1,prompt:'Câu hỏi <script> & "test"'});
assert.match(html,/&lt;script&gt;/);assert(!html.includes('<script>'));assert.match(html,/data-delete-confirm disabled/);assert.match(html,/type="checkbox"/);assert.match(html,/lịch sử/);assert.match(html,/kỷ lục/);assert.match(html,/Thu hồi/);
const src=await readFile(new URL('../src/admin-trivia-delete.ts',import.meta.url),'utf8');assert.match(src,/q\.revision,confirm:true/);assert.match(src,/if\(busy\|\|!ack\.checked\)return/);assert.match(src,/dialog\.showModal\(\)/);assert(!/window\.confirm|alert\(/.test(src));
console.log('TRIVIA_DELETE_UI_PASS');
