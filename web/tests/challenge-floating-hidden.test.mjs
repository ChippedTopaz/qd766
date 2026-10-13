import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const app=readFileSync(new URL('../src/app.ts',import.meta.url),'utf8');
const css=readFileSync(new URL('../bento.css',import.meta.url),'utf8');
assert.match(app,/data-challenge-board hidden>BXH thách đấu/);
assert.match(css,/\.challenge-floating\[hidden\]\{display:none!important\}/);
assert.match(app,/openChallengeBoard\(\)/,'Leaderboard implementation remains available');
assert.match(app,/bindChallengeNotifications\(/,'Incoming challenge notifications are preserved');
console.log('CHALLENGE_FLOATING_HIDDEN_PASS: temporary launcher-only hiding');
