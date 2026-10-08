import {setFormulaConfiguration,type FormulaConfiguration} from './formula-reference.js';
let pending:Promise<boolean>|null=null,lastLoaded=0;
// Lazy load only on the reference screen; no impact on dashboard startup.
export function loadFormulaConfiguration():Promise<boolean> {
 if(pending)return pending;
 if(Date.now()-lastLoaded<10000)return Promise.resolve(false);
 pending=(async()=>{
  const response=await fetch('/api/v1/formula-reference',{cache:'no-store',signal:AbortSignal.timeout(12000)});
  if(!response.ok)throw new Error('Không tải được nội dung Công thức tính mới nhất.');
  const value=await response.json() as {configuration:FormulaConfiguration};
  setFormulaConfiguration(value.configuration);lastLoaded=Date.now();return true;
 })().finally(()=>{pending=null;});return pending;
}
