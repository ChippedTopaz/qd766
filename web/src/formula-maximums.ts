import type {GroupId} from './types.js';

/** Values from docs/metrics.m0.json, except the payment 2+2+6 breakdown
 * explicitly approved after reconciliation with API and DVCQG charts. */
export interface FormulaMaximum {name:string; maximum:number|null; metricCode?:string; formulaId?:string; sourceRow:number}
export const formulaMaximums:Record<GroupId,FormulaMaximum[]>={
 transparency:[
  {name:'TTHC công bố đúng hạn',maximum:6,metricCode:'PUBLISH_ON_TIME',formulaId:'1.1',sourceRow:2},
  {name:'TTHC cập nhật, công khai đúng hạn',maximum:4,metricCode:'PUBLIC_UPDATE_ON_TIME',formulaId:'1.2',sourceRow:3},
  {name:'TTHC công khai đầy đủ nội dung',maximum:2,metricCode:'PUBLIC_CONTENT_FULL',formulaId:'1.3',sourceRow:4},
  {name:'Hồ sơ đồng bộ lên Cổng DVCQG',maximum:6,metricCode:'DOSSIER_SYNC',formulaId:'1.4',sourceRow:5},
 ],
 'dvc-progress-tree':[
  {name:'Hồ sơ xử lý trước hạn, đúng hạn',maximum:20,formulaId:'2.1',sourceRow:6},
 ],
 'provide-online-tree':[
  {name:'Hồ sơ DVCTT toàn trình trên tổng hồ sơ TTHC đủ điều kiện toàn trình',maximum:12,sourceRow:7},
  {name:'TTHC cung cấp dịch vụ công trực tuyến',maximum:null,formulaId:'3.1',sourceRow:8},
  {name:'TTHC cung cấp DVCTT chủ động theo mức độ',maximum:null,sourceRow:9},
  {name:'Hồ sơ dịch vụ công chủ động theo mức độ',maximum:null,sourceRow:10},
  {name:'Hồ sơ theo hình thức nộp',maximum:null,formulaId:'3.3',sourceRow:11},
 ],
 'dossier-digitized':[
  {name:'Hồ sơ có kết quả giải quyết điện tử',maximum:6,metricCode:'ORIGINAL_RESULT_AVAILABLE',formulaId:'4.1',sourceRow:12},
  {name:'Hồ sơ thực hiện số hóa thành phần',maximum:4,metricCode:'SO_HOA_GIAY_TO_GIAI_QUYET',formulaId:'4.2',sourceRow:13},
  {name:'Cung cấp dịch vụ chứng thực bản sao điện tử từ bản chính',maximum:2,metricCode:'ELECTRONIC_CERTIFIED_COPY',sourceRow:14},
  {name:'Hồ sơ khai thác, sử dụng lại dữ liệu số hóa',maximum:2,metricCode:'REUSED_DIGITIZED_DATA',formulaId:'4.3',sourceRow:15},
  {name:'Hồ sơ số hóa kết nối, chia sẻ để tái sử dụng',maximum:4,metricCode:'SYNCED_WITH_DVCQG_PERSONAL_STORAGE',formulaId:'4.4',sourceRow:16},
  {name:'Hồ sơ sử dụng thông tin từ CSDL dân cư',maximum:2,metricCode:'CITIZEN_DATA_CONNECTED_DOSSIER',formulaId:'4.5b',sourceRow:17},
  {name:'TTHC kết nối, chia sẻ dữ liệu dân cư',maximum:2,metricCode:'CITIZEN_DATA_CONNECTED_FORMALITY',formulaId:'4.5a',sourceRow:18},
 ],
 'handling-satisfaction':[
  {name:'Hài lòng về cắt giảm, phân cấp, đơn giản hóa TTHC',maximum:null,sourceRow:19},
  // API metric names are used to avoid conflating old spreadsheet descriptions.
  {name:'Phản ánh, kiến nghị về quy định, TTHC',maximum:0,metricCode:'PETITION_CLASSIFICATION_TTHC',sourceRow:20},
  {name:'Phản ánh, kiến nghị về cán bộ, công chức',maximum:0,metricCode:'PETITION_CLASSIFICATION_STAFF',sourceRow:21},
  {name:'Phản ánh, kiến nghị xử lý đúng hạn',maximum:6,metricCode:'PETITION_PROCESSING_ON_TIME',formulaId:'5.2',sourceRow:22},
  {name:'Hài lòng trong xử lý phản ánh, kiến nghị',maximum:6,metricCode:'PETITION_HANDLING_SATISFACTION',formulaId:'5.3',sourceRow:23},
  {name:'Hài lòng trong tiếp nhận, giải quyết TTHC',maximum:6,metricCode:'DOSSIER_RECEIVING_SATISFACTION',formulaId:'5.4',sourceRow:24},
 ],
 'formality-online-payment-tree':[
  // Three components reconciled with API and DVCQG charts; approved 08/10/2026.
  {name:'TTHC có nghĩa vụ tài chính được cung cấp trên Cổng DVCQG',maximum:2,formulaId:'3.5',sourceRow:25},
  {name:'TTHC có giao dịch thanh toán trực tuyến',maximum:2,formulaId:'3.5b',sourceRow:25},
  {name:'Hồ sơ thanh toán trực tuyến',maximum:6,formulaId:'3.6',sourceRow:25},
 ],
};
export function maximumText(maximum:number|null):string{
 return maximum===null?'Chưa xác định':maximum===0?'0 điểm · Chỉ theo dõi':`${maximum} điểm`;
}
