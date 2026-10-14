import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {indicatorRowClick} from '../dist/daily-indicator-comparison.js';

// Cells/blank row area and touch-generated clicks activate the row.
for(const detail of [0,1]){
 assert.equal(indicatorRowClick({detail,target:{closest(){return null}}}),true);
}
for(const button of ['button.row-link','button.daily-indicator-name']){
 const event={target:{closest(){return {matches(selector){return selector.split(',').includes(button)}}}}};
 assert.equal(indicatorRowClick(event),true,'Name button/native keyboard click bubbles to the row');
}
for(const control of ['a','button.export','input','select','textarea','label','summary','[role="button"]','[contenteditable="true"]']){
 const event={target:{closest(selector){
  assert.match(selector,/button,a,input,select,textarea/);
  return {matches(){return false}};
 }}};
 assert.equal(indicatorRowClick(event),false,control+' keeps its independent interaction');
}
const source=readFileSync(new URL('../src/daily-indicator-comparison.ts',import.meta.url),'utf8');
assert.match(source,/<tr class="daily-selectable-row/);
assert.doesNotMatch(source,/<button[^\n]*data-daily-indicator-row=/,'Bind once on tr, not twice on tr and name button');
assert.match(source,/class="daily-indicator-name" aria-pressed=/,'Keep the native keyboard-accessible name button and selection state');
const css=readFileSync(new URL('../bento.css',import.meta.url),'utf8');
assert.match(css,/daily-selectable-row\{cursor:pointer\}/);
assert.match(css,/daily-selectable-row:focus-within/);
console.log('INDICATOR_ROW_CLICK_PASS: cells/row area, keyboard name button, independent controls, single row binding and visual affordance');
