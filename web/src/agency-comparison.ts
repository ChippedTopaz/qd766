import type {GroupId, Snapshot, UnitOption} from './types.js';

export type AgencyLevel = 'PROVINCE' | 'COMMUNE';
export interface AgencyComparisonRow {
  id:string; name:string; level:AgencyLevel;
  scores:Partial<Record<GroupId,number>>; total:number|null;
  rank:number|null; scoreChange:number|null; rankChange:number|null;
}
const finite=(value:unknown):value is number=>typeof value==='number'&&Number.isFinite(value);

/** Public score inventory in the authorized province, not a detail-selection allowlist. */
export function agencyComparisonUnits(snapshot:Snapshot):UnitOption[]{
  const units=new Map<string,UnitOption>();
  for(const dataset of snapshot.datasets)for(const entity of dataset.children){
    if(entity.departmentLevel!=='PROVINCE'&&entity.departmentLevel!=='COMMUNE')continue;
    if(!units.has(entity.departmentId))units.set(entity.departmentId,{
      departmentId:entity.departmentId,departmentName:entity.departmentName,
      departmentType:entity.departmentType,departmentLevel:entity.departmentLevel,
    });
  }
  return [...units.values()];
}

/** Union all source groups; missing scores are not zero. The allowlist is mandatory. */
export function agencyComparison(snapshot:Snapshot, previous:Snapshot|null, groups:GroupId[], allowed:UnitOption[]):AgencyComparisonRow[] {
  const inventory=(source:Snapshot):AgencyComparisonRow[]=>{
    const units=new Map(allowed.map(item=>[item.departmentId,item]));
    const rows=new Map<string,AgencyComparisonRow>();
    const maxima=new Map<string,Set<GroupId>>();
    for(const dataset of source.datasets)for(const entity of dataset.children){
      const option=units.get(entity.departmentId);
      if(!option||(option.departmentLevel!=='PROVINCE'&&option.departmentLevel!=='COMMUNE'))continue;
      let row=rows.get(entity.departmentId);
      if(!row){row={id:entity.departmentId,name:option.departmentName,level:option.departmentLevel,scores:{},total:null,rank:null,scoreChange:null,rankChange:null};rows.set(row.id,row);}
      if(finite(entity.apiScore))row.scores[dataset.group]=entity.apiScore;
      if(finite(entity.apiMaxScore)){
        if(!maxima.has(row.id))maxima.set(row.id,new Set());
        maxima.get(row.id)!.add(dataset.group);
      }
    }
    for(const row of rows.values()){
      // A complete total requires all six official groups, never a partial sum for TTHC.
      if(groups.length===6&&groups.every(group=>finite(row.scores[group])&&maxima.get(row.id)?.has(group)))row.total=groups.reduce((sum,group)=>sum+row.scores[group]!,0);
    }
    for(const row of rows.values())if(row.total!==null)row.rank=1+[...rows.values()].filter(other=>other.level===row.level&&other.total!==null&&other.total>row.total!+.005).length;
    return [...rows.values()];
  };
  const rows=inventory(snapshot);
  // Period selection is validated by caller; additionally forbid scope/TTHC mismatches.
  const comparable=previous&&previous.scope===snapshot.scope&&previous.formalityId===snapshot.formalityId;
  const prior=new Map((comparable?inventory(previous):[]).map(row=>[row.id,row]));
  for(const row of rows){
    const before=prior.get(row.id);
    if(before?.level!==row.level)continue;
    if(row.total!==null&&before.total!==null)row.scoreChange=row.total-before.total;
    // Rank deltas require exactly the same fully scored cohort in both periods.
    const currentPeers=rows.filter(item=>item.level===row.level&&item.total!==null).map(item=>item.id).sort();
    const priorPeers=[...prior.values()].filter(item=>item.level===row.level&&item.total!==null).map(item=>item.id).sort();
    if(row.rank!==null&&before.rank!==null&&currentPeers.join('|')===priorPeers.join('|'))row.rankChange=before.rank-row.rank;
  }
  return rows;
}

export function orderAgencies(rows:AgencyComparisonRow[], dimension:'total'|GroupId, query:string, direction:'asc'|'desc'='desc'):AgencyComparisonRow[]{
  const plain=(value:string)=>value.toLocaleLowerCase('vi').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d');
  const needle=plain(query.trim());
  return rows.filter(row=>plain(row.name).includes(needle)).sort((a,b)=>{
    const left=dimension==='total'?a.total:a.scores[dimension]??null;
    const right=dimension==='total'?b.total:b.scores[dimension]??null;
    return left===null?(right===null?a.name.localeCompare(b.name,'vi'):1):right===null?-1:
      (direction==='asc'?left-right:right-left)||a.name.localeCompare(b.name,'vi');
  });
}
