import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
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
const app=readFileSync(new URL('../src/app.ts',import.meta.url),'utf8');
assert.match(app,/class="overview-intro" aria-label="Cơ quan và kỳ báo cáo"/);
assert.match(app,/\$\{overviewTabs\(overviewTab\)\}\s*\$\{overviewStatus\(\)\}<\/section>/);
assert.match(app,/if\(tab==="details"\)\{state\.selectedGroup=null;state\.selectedMetric=null;\}/);
const navigator=app.slice(app.indexOf('function overviewGroupNavigator('),app.indexOf('function overviewStatus('));
assert.doesNotMatch(navigator,/data-group-export|<span>Nhóm chỉ tiêu<\/span>/);
assert.match(navigator,/--group-accent/);
assert.match(app,/groupTableHeading\("Điểm 6 nhóm chỉ tiêu"\)/);
assert.match(app,/groupTableHeading\("Kết quả các chỉ tiêu thành phần"\)/);
assert.match(app,/state\.selectedGroup=el\.dataset\.groupDetail as GroupId;state\.selectedMetric=null;overviewTab="details"/);
console.log('Group detail UI PASS: summary default, direct group selection, table-header export and colored navigator');
