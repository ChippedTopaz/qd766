export type AccountScope={email:string|null;name:string;provinceId:string|null;unitId:string|null;provinceName?:string|null;unitName?:string|null};
export function filterAdminAccounts<T extends AccountScope>(accounts:T[],search:string,province:string,unit:string):T[]{
  const query=search.trim().toLocaleLowerCase("vi");
  return accounts.filter(a=>(!province||a.provinceId===province)&&(!unit||a.unitId===unit)&&
    `${a.email??""} ${a.name} ${a.provinceName??""} ${a.unitName??""}`.toLocaleLowerCase("vi").includes(query));
}
export function accountUnitOptions(accounts:AccountScope[],province:string):{id:string;name:string}[]{
  const units=new Map(accounts.filter(a=>a.provinceId===province&&a.unitId).map(a=>[a.unitId!,a.unitName??"Chưa xác định cơ quan"]));
  return [...units].map(([id,name])=>({id,name})).sort((a,b)=>a.name.localeCompare(b.name,"vi"));
}
