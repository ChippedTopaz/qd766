import assert from 'node:assert/strict';
import {paragraphAtCaret,previewFieldSelectors,businessEditorLines,updateBusinessEditor} from '../dist/admin-formula-focus.js';
import {defaultFormulaConfiguration} from '../dist/formula-reference.js';
assert.equal(paragraphAtCaret('Một\nHai\nBa',0,['Một','Hai','Ba']),0);
assert.equal(paragraphAtCaret('Một\nHai\nBa',5,['Một','Hai','Ba']),1);
assert.equal(paragraphAtCaret('Một\n\nBa',5,['Một','','Ba']),2);
assert.equal(paragraphAtCaret('Dòng 1\nDòng 2\nĐoạn sau',9,['Dòng 1\nDòng 2','Đoạn sau']),0);
assert.equal(paragraphAtCaret('Dòng 1\nDòng 2\nĐoạn sau',15,['Dòng 1\nDòng 2','Đoạn sau']),1);
assert.match(previewFieldSelectors.numerator,/span:first-child/);
assert.match(previewFieldSelectors.denominator,/span:last-child/);
assert.notEqual(previewFieldSelectors.numerator,previewFieldSelectors.denominator);
assert.equal(previewFieldSelectors.title,'.formula-card-heading h3');
for(const id of ['3.2','4.5a']){
 const formula=defaultFormulaConfiguration().groups.flatMap(g=>g.items).find(f=>f.id===id);
 const original=structuredClone(formula),text=businessEditorLines(formula).join('\n');
 updateBusinessEditor(formula,text);assert.deepEqual(formula,original);
 updateBusinessEditor(formula,text+'\nCập nhật');assert.equal(formula.businessHeading,'');assert.equal(formula.versionNote,'');
 assert.deepEqual(businessEditorLines(formula),[...businessEditorLines(original),'Cập nhật']);assert.deepEqual(formula.document,original.document);
}
console.log('FORMULA_FOCUS_OK: correct field selectors and cursor-to-paragraph mapping');
