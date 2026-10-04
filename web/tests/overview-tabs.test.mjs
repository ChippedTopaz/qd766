import assert from "node:assert/strict";
import {adjacentGroup,overviewTabs} from "../dist/overview-tabs.js";
const groups=["a","b","c","d","e","f"];
assert.equal(adjacentGroup(groups,"a",-1),"f");
assert.equal(adjacentGroup(groups,"f",1),"a");
assert.equal(adjacentGroup(groups,"b",1),"c");
assert.equal(adjacentGroup(groups,null,1),"a");
assert.equal(adjacentGroup(groups,null,-1),"f");
assert.equal(adjacentGroup([],null,1),null);
for(const id of ["overview","details","analysis"]){
  const html=overviewTabs(id);
  assert.equal((html.match(/role="tab"/g)||[]).length,3);
  assert.equal((html.match(/aria-selected="true"/g)||[]).length,1);
  assert.match(html,new RegExp(`data-overview-tab="${id}" aria-selected="true"`));
}
console.log("Overview tabs PASS: accessible tabs, six-group navigation and wraparound");
