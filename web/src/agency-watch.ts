import type {Snapshot} from './types.js';
export const WATCH_LIMIT=5;
export function watchChoiceMatches<T extends {departmentName:string}>(units:T[],query:string):T[]{
 const plain=(text:string)=>text.toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');
 const needle=plain(query.trim());
 return units.filter(u=>plain(u.departmentName).includes(needle)).sort((a,b)=>a.departmentName.localeCompare(b.departmentName,'vi'));
}
const valid=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v)&&v>=0;
export function similarReceived(snapshot:Snapshot,ownId:string,peerId:string):boolean|null{
 if(snapshot.scope!=='all')return null;
 const progress=snapshot.datasets.find(g=>g.group==='dvc-progress-tree');
 if(!progress)return null;
 const entities=[progress.root,...progress.children];
 const own=entities.find(e=>e.departmentId===ownId),peer=entities.find(e=>e.departmentId===peerId);
 const a=own?.parameters.totalReceived,b=peer?.parameters.totalReceived;
 if(valid(a)&&valid(b))return b>=a*.8&&b<=a*1.2;
 const permitted=peer as (typeof peer & {similarReceivedVolume?:boolean|null});
 return permitted?.similarReceivedVolume??null;
}
export function watchTone(value:number|null|undefined,baseline:number|null|undefined){
 if(value==null||baseline==null||!Number.isFinite(value)||!Number.isFinite(baseline))return 'watch-missing';
 const delta=Math.round((value-baseline)*100)/100;
 return delta>0?'watch-higher':delta<0?'watch-lower':'watch-equal';
}
async function watchRequest(provinceId:string,csrf?:string,ids?:string[]):Promise<string[]>{
 const response=await fetch('/api/v1/me/agency-watch'+(ids?'':'?province_id='+encodeURIComponent(provinceId)),{
  cache:'no-store',signal:AbortSignal.timeout(15000),
  ...(ids?{method:'POST',headers:{'Content-Type':'application/json','X-QD766-CSRF':csrf??''},body:JSON.stringify({provinceId,unitIds:ids})}:{})
 });
 const body=await response.json();
 if(!response.ok)throw new Error(typeof body.detail==='string'?body.detail:'Chưa đọc hoặc lưu được danh sách theo dõi.');
 if(!Array.isArray(body.unitIds)||body.unitIds.length>WATCH_LIMIT||body.unitIds.some((id:unknown)=>typeof id!=='string')||new Set(body.unitIds).size!==body.unitIds.length)throw new Error('Danh sách theo dõi trả về không hợp lệ.');
 return body.unitIds;
}
export const readWatch=(provinceId:string)=>watchRequest(provinceId);
export function saveWatch(provinceId:string,ids:string[],csrf:string):Promise<string[]>{
 if(ids.length>WATCH_LIMIT||new Set(ids).size!==ids.length)return Promise.reject(new Error('Chỉ chọn tối đa 5 cơ quan, không trùng nhau.'));
 return watchRequest(provinceId,csrf,ids);
}
