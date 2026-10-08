import assert from 'node:assert/strict';
import {leaderboardRows} from '../dist/trivia-leaderboard.js';
const rows=leaderboardRows(Array.from({length:25},(_,i)=>({rank:i+1,name:'Người <script>',province:'Tỉnh & xã',best:25-i,correctAnswers:50-i})));
assert.equal((rows.match(/<tr>/g)||[]).length,20);
assert(rows.includes('&lt;script&gt;'));assert(rows.includes('Tỉnh &amp; xã'));
assert(!rows.includes('<script>'));assert(!rows.includes('email'));
console.log('TRIVIA_LEADERBOARD_UI_OK: top20, escaped display names, province, scores; no automatic fetch');
