import type {Formula} from './formula-reference.js';

export const previewFieldSelectors:Record<string,string>={
 title:'.formula-card-heading h3',maximum:'.maximum-badge',target:'.formula-card-meta, .formula-score-equation',
 equationLabel:'.formula-math-section > .formula-equation > span:first-child',
 numerator:'.formula-math-section > .formula-equation > .formula-fraction > span:first-child, .formula-math-section > .formula-equation > strong',
 denominator:'.formula-math-section > .formula-equation > .formula-fraction > span:last-child',
 multiplier:'.formula-math-section > .formula-equation > span:last-child',
 symbols:'.formula-math-section > .formula-symbols',mathNote:'.formula-math-section > .formula-version-note',
 businessHeading:'.formula-business > .formula-business-heading:first-of-type',versionNote:'.formula-business > .formula-version-note',
 clarification:'.formula-clarification',
};
export function businessEditorLines(formula:Formula):string[]{
 return [...[formula.businessHeading,formula.versionNote].filter((line):line is string=>!!line),...formula.businessLines??[]];
}
export function updateBusinessEditor(formula:Formula,value:string):void {
 if(value===businessEditorLines(formula).join('\n'))return;
 // Merge legacy annotations into the single editable narrative only when it is edited.
 formula.businessLines=value.split('\n');formula.businessHeading='';formula.versionNote='';
}
export function paragraphAtCaret(text:string,caret:number,paragraphs:string[]):number {
 let start=0;
 for(let index=0;index<paragraphs.length;index++){
  const end=start+paragraphs[index]!.length;
  if(caret<=end)return index;
  start=end+1;
 }
 return Math.max(0,paragraphs.length-1);
}

/** Decoration applies to the admin preview only, never public reference markup or saved data. */
export function highlightFormulaPreview(panel:HTMLElement,editor:HTMLElement|null,formula:Formula):void {
 panel.querySelectorAll('.formula-preview-highlight').forEach(el=>el.classList.remove('formula-preview-highlight'));
 if(!editor)return;
 const field=editor.dataset.field;
 let targets:HTMLElement[]=[];
 if(field&&previewFieldSelectors[field])targets=Array.from(panel.querySelectorAll<HTMLElement>(previewFieldSelectors[field]));
 if(editor instanceof HTMLTextAreaElement&&['businessLines','notes','dataSources'].includes(field??'')){
  const rows=field==='businessLines'?businessEditorLines(formula):field==='notes'?formula.document.notes:formula.document.dataSources;
  const paragraphs=field==='businessLines'?Array.from(panel.querySelectorAll<HTMLElement>('.formula-business > p')):
   Array.from(panel.querySelectorAll<HTMLElement>(field==='notes'?'.formula-accordion-notes .formula-accordion-body > p':'.formula-accordion-sources .formula-accordion-body > p'));
  const sourceIndex=paragraphAtCaret(editor.value,editor.selectionStart,rows);
  const renderedIndex=rows.slice(0,sourceIndex+1).filter(line=>line.trim()).length-1;
  const paragraph=paragraphs[Math.max(0,Math.min(renderedIndex,paragraphs.length-1))];
  if(paragraph)targets=[paragraph];
 }
 if(editor.dataset.extra){
  const row=editor.closest('[data-extra-row]'),index=Array.from(editor.closest('form')!.querySelectorAll('[data-extra-row]')).indexOf(row!);
  const equation=panel.querySelectorAll<HTMLElement>('.formula-math-section > .formula-extra > .formula-equation')[index];
  const selector=editor.dataset.extra==='label'?':scope > span:first-child':editor.dataset.extra==='numerator'?'.formula-fraction > span:first-child, .formula-extra-expression > span:first-of-type':editor.dataset.extra==='denominator'?'.formula-fraction > span:last-child, .formula-extra-expression > span:last-of-type':editor.dataset.extra==='multiplier'?':scope > span:last-child':null;
  const target=selector?equation?.querySelector<HTMLElement>(selector):equation;if(target)targets=[target];
 }
 const globalKey=['group-name','group-maximum','source-name','source-version','source-guide'].find(key=>editor.hasAttribute('data-'+key));
 if(globalKey)targets=Array.from(panel.querySelectorAll<HTMLElement>('[data-preview-'+globalKey+']'));
 if(!targets.length&&field){
  const fallback=field==='denominator'||field==='symbols'||field==='mathNote'?'.formula-math-section':
   field==='clarification'||field==='notes'?'.formula-accordion-notes':field==='dataSources'?'.formula-accordion-sources':
   field==='businessHeading'||field==='versionNote'||field==='businessLines'?'.formula-accordion-calculation':null;
  if(fallback)targets=Array.from(panel.querySelectorAll<HTMLElement>(fallback));
 }
 targets.forEach(target=>{
  target.classList.add('formula-preview-highlight');
  for(let parent:HTMLElement|null=target;parent&&parent!==panel;parent=parent.parentElement)if(parent instanceof HTMLDetailsElement)parent.open=true;
 });
 const first=targets[0];if(!first)return;
 const box=first.getBoundingClientRect(),viewport=panel.getBoundingClientRect();
 if(panel.scrollHeight>panel.clientHeight&&(box.top<viewport.top+12||box.bottom>viewport.bottom-12)){
  panel.scrollTo({top:Math.max(0,panel.scrollTop+box.top-viewport.top-24),behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
 }
}
