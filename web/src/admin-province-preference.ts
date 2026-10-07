type Account={id?:string;role?:string}|null;
type Store=Pick<Storage,'getItem'|'setItem'|'removeItem'>;
const validProvince=(id:string)=>/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
const key=(account:Account)=>account?.role==='admin'&&account.id?'qd766:last-province:'+account.id:null;
export function lastAdminProvince(account:Account,store?:Store):string|null{
  const name=key(account);if(!name)return null;
  try{const id=(store??globalThis.localStorage)?.getItem(name);return id&&validProvince(id)?id:null}catch{return null}
}
export function rememberAdminProvince(account:Account,id:string,store?:Store):void{
  const name=key(account);if(!name||!validProvince(id))return;
  try{(store??globalThis.localStorage)?.setItem(name,id)}catch{/* Storage blocked/full must never prevent loading. */}
}
export function clearAdminProvince(account:Account,store?:Store):void{
  const name=key(account);if(!name)return;
  try{(store??globalThis.localStorage)?.removeItem(name)}catch{/* Preference only; no account or access-policy changes. */}
}
