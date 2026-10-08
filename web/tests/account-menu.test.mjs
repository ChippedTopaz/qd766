import assert from "node:assert/strict";
import {pathToFileURL} from "node:url";
const {accountMenu}=await import(pathToFileURL(process.argv[2]).href);
const html=accountMenu({name:'Nguyễn <script>',credits:94});
assert.ok(!html.includes("<script>"));
assert.match(html,/Thông tin tài khoản/);
assert.match(html,/Usage \(credits\)/);
assert.match(html,/data-action="logout"/);
assert.match(html,/aria-expanded="false"/);
assert.match(html,/94 credit khả dụng/);
assert.match(html,/account-avatar/);
// Anchor to the account button wrapper, not the zone containing the entire Trivia card.
assert.match(html,/<div class="account-zone"><div class="account-controls"><button/);
assert.match(html,/\.account-controls\{position:relative;flex:0 0 auto;width:100%;min-width:0\}/);
assert.match(html,/\.account-popover\{position:absolute;bottom:calc\(100% \+ 8px\)/);
console.log("Account menu presentation PASS");
