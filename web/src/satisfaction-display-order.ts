import type {GroupId,Metric} from './types.js';

// Presentation only: stable ordering of rendered rows, never sort or mutate API metrics.
const satisfactionOrder=[
 'PETITION_PROCESSING_ON_TIME','PETITION_HANDLING_SATISFACTION','DOSSIER_RECEIVING_SATISFACTION',
 'totalDossiers','totalPetitions','classifiedPetitions',
 'PETITION_CLASSIFICATION_STAFF','PETITION_CLASSIFICATION_TTHC',
];
const digitizedLabels:Record<string,string>={
 ORIGINAL_RESULT_AVAILABLE:'Tỷ lệ hồ sơ TTHC có cấp kết quả giải quyết TTHC điện tử',
 SO_HOA_GIAY_TO_GIAI_QUYET:'Tỷ lệ hồ sơ TTHC thực hiện số hóa hồ sơ',
 REUSED_DIGITIZED_DATA:'Tỷ lệ hồ sơ khai thác, sử dụng lại thông tin, dữ liệu số hóa',
 SYNCED_WITH_DVCQG_PERSONAL_STORAGE:'Tỷ lệ hồ sơ TTHC được số hóa có kết nối, chia sẻ dữ liệu phục vụ tái sử dụng',
 CITIZEN_DATA_CONNECTED_FORMALITY:'Tỷ lệ TTHC triển khai kết nối, chia sẻ dữ liệu dân cư phục vụ giải quyết TTHC',
 CITIZEN_DATA_CONNECTED_DOSSIER:'Tỷ lệ hồ sơ TTHC có sử dụng thông tin, dữ liệu dân cư',
 ELECTRONIC_CERTIFIED_COPY:'Tỷ lệ cung cấp dịch vụ chứng thực bản sao điện tử từ bản chính',
};
export function detailMetricName(group:GroupId,metric:Pick<Metric,'code'|'name'>):string{
 return group==='dossier-digitized'?(digitizedLabels[metric.code]??metric.name):metric.name;
}
export function orderSatisfactionRows<T extends {key:string}>(group:GroupId,rows:readonly T[]):T[]{
 const result=[...rows];
 const order=group==='handling-satisfaction'?satisfactionOrder:group==='dossier-digitized'?Object.keys(digitizedLabels):null;
 if(order){
  const rank=(key:string)=>{const index=order.indexOf(key);return index<0?order.length:index;};
  result.sort((a,b)=>rank(a.key)-rank(b.key));
 }
 return result;
}
