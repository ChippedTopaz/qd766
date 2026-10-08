import type { GroupId } from './types.js';
import { groupIcon, groupColors, icon } from './bento.js';
import {formulaMaximums,maximumText} from './formula-maximums.js';
import {formulaDocument, type FormulaDocumentRow} from './formula-document.js';

export const formulaSource = { name: formulaDocument.name, sha256:formulaDocument.sha256, version: 'Đối chiếu ngày 07/10/2026' };
export interface FormulaEquation { id:string; numerator:string; denominator:string; multiplier?:string; target?:number|null; caution?:string }
export interface FormulaExtra {label:string;numerator:string;denominator:string;operator?:'add'|'subtract'|'multiply'|'divide';multiplier?:string}
export interface Formula extends FormulaEquation { title:string; rules:string[]; document:FormulaDocumentRow; maximum?:number|null; equationLabel?:string; clarification?:string; businessLines?:string[]; businessHeading?:string; versionNote?:string; mathNote?:string; symbols?:string; extras?:FormulaExtra[] }
export interface FormulaGroup { id:GroupId; name:string; maximum:number; items:Formula[] }
export interface FormulaConfiguration {source:typeof formulaSource;groups:FormulaGroup[];guide:string[]}
let activeConfiguration:FormulaConfiguration|null=null;
export function setFormulaConfiguration(value:FormulaConfiguration):void {activeConfiguration=value;}
const formulaDefinitions: {id:GroupId; name:string; maximum:number; items:FormulaEquation[]}[] = [
 {id:'transparency',name:'Công khai, minh bạch',maximum:18,items:[
  {id:'1.1',numerator:'TTHC công bố đúng hạn',denominator:'TTHC đã công bố trong kỳ'},
  {id:'1.2',numerator:'TTHC công khai đúng hạn trên CSDL quốc gia',denominator:'TTHC phải cập nhật, công khai trong kỳ',caution:'Điều kiện “Ngày QĐ ≤ ngày cuối kỳ + 10/5 ngày làm việc” trong tài liệu cần được làm rõ trước khi tự tái dựng danh sách hồ sơ.'},
  {id:'1.3',numerator:'TTHC đầy đủ các bộ phận cấu thành',denominator:'TTHC đã cập nhật, công khai trên CSDL quốc gia',caution:'Tài liệu nêu không tính theo thời gian nhưng phần lưu ý chung lại ghi theo kỳ. Trang này giữ quy tắc nghiệp vụ cụ thể và ghi nhận khác biệt.'},
  {id:'1.4',numerator:'Hồ sơ đã đồng bộ có ngày tiếp nhận trong kỳ',denominator:'Giá trị lớn hơn giữa hồ sơ tiếp nhận trên BCQG và DVCQG'},
 ]},
 {id:'dvc-progress-tree',name:'Tiến độ giải quyết',maximum:20,items:[
  {id:'2.1',numerator:'Hồ sơ đã và đang xử lý đúng hạn hoặc trong hạn',denominator:'Hồ sơ tiếp nhận, xử lý trong kỳ',caution:'Tài liệu xác định tỷ lệ nhưng không ghi phép quy đổi điểm/điểm tối đa riêng. Phép nhân tỷ lệ × điểm tối đa đang có là cách đối chiếu trước đây, không phải phân bổ điểm được xác nhận bởi tài liệu này.'},
  {id:'2.2',numerator:'Tổng thời gian giải quyết các hồ sơ hoàn thành',denominator:'Tổng số hồ sơ TTHC hoàn thành',multiplier:'',caution:'Trường avgProcessingDays hiện có được hiển thị theo ngày; không thay thế được toàn bộ chỉ tiêu đa đơn vị này.'},
 ]},
 {id:'provide-online-tree',name:'Dịch vụ công trực tuyến',maximum:12,items:[
  {id:'3.1',numerator:'TTHC có DVCTT một phần hoặc toàn trình',denominator:'TTHC thuộc thẩm quyền giải quyết',target:80},
  {id:'3.2',numerator:'DVC có hồ sơ tiếp nhận trực tuyến của TTHC',denominator:'Số DVC của TTHC',caution:'Phần cũ ghi ẩn khi chọn TTHC, phần Update lại mô tả theo TTHC; cần xác nhận phạm vi. Tài liệu không nêu ngưỡng 100% hoặc điểm tối đa 4 như cấu hình suy luận trước đây.'},
  {id:'3.3',numerator:'Hồ sơ trực tuyến đáp ứng điều kiện kết quả điện tử',denominator:'Tổng hồ sơ tiếp nhận trong kỳ',multiplier:'× hệ số đồng bộ × 100%',target:50,caution:'Không đủ căn cứ để dùng channelOnlineSum đơn độc khi chưa biết đã lọc kết quả điện tử và đã áp dụng hệ số đồng bộ hay chưa.'},
 ]},
 {id:'formality-online-payment-tree',name:'Thanh toán trực tuyến',maximum:10,items:[
  {id:'3.5',numerator:'TTHC có yêu cầu nghĩa vụ tài chính được cung cấp trên Cổng DVCQG',denominator:'Tổng TTHC có yêu cầu nghĩa vụ tài chính',target:80},
  {id:'3.5b',numerator:'TTHC có giao dịch thanh toán trực tuyến',denominator:'Tổng TTHC có yêu cầu nghĩa vụ tài chính (không trùng lặp)',target:80},
  {id:'3.6',numerator:'Hồ sơ thanh toán trực tuyến thành công',denominator:'Hồ sơ có nghĩa vụ tài chính'},
 ]},
 {id:'dossier-digitized',name:'Số hóa hồ sơ',maximum:22,items:[
  {id:'4.1',numerator:'Hồ sơ có đường dẫn tệp kết quả điện tử hợp lệ',denominator:'Hồ sơ thuộc TTHC yêu cầu trả kết quả bằng văn bản, giấy tờ'},
  {id:'4.2',numerator:'Hồ sơ được số hóa và có kết quả điện tử khi TTHC yêu cầu',denominator:'Hồ sơ TTHC thuộc thẩm quyền giải quyết',target:80},
  {id:'4.3',numerator:'Hồ sơ có ít nhất một thành phần sử dụng lại dữ liệu số hóa',denominator:'Hồ sơ có ngày tiếp nhận trong kỳ',target:80},
  {id:'4.4',numerator:'Hồ sơ có thành phần lấy từ kho cá nhân hoặc kết quả điện tử đồng bộ lên danh mục',denominator:'Hồ sơ có ngày tiếp nhận trong kỳ',caution:'Tài liệu chưa nêu điểm tối đa hoặc cách quy đổi điểm riêng.'},
  {id:'4.5a',numerator:'TTHC có kết nối, chia sẻ dữ liệu dân cư',denominator:'TTHC có đối tượng thực hiện là người dân'},
  {id:'4.5b',numerator:'Hồ sơ sử dụng thông tin, dữ liệu CSDL dân cư',denominator:'Tổng hồ sơ TTHC',caution:'Hai tỷ lệ trong mục 4.5 có mẫu số khác nhau, không gộp thành một tỷ lệ.'},
 ]},
 {id:'handling-satisfaction',name:'Mức độ hài lòng',maximum:18,items:[
  {id:'5.1',numerator:'PAKN đã tiếp nhận thuộc phân loại đang xét',denominator:'Tổng PAKN trong kỳ theo đơn vị'},
  {id:'5.2',numerator:'PAKN đã xử lý đúng hạn và đang xử lý trong hạn',denominator:'PAKN tiếp nhận, xử lý trong kỳ',caution:'Dòng tỷ lệ trong tài liệu bị lỗi văn bản; tử số ở đây là diễn giải từ các quy tắc bên dưới, cần xác nhận trước khi tính tự động.'},
  {id:'5.3',numerator:'Tổng PAKN − PAKN không hài lòng, phản ánh tiếp hoặc quá hạn',denominator:'Tổng PAKN tiếp nhận lần đầu trong kỳ',caution:'Tài liệu dẫn “chỉ tiêu 5c” không khớp số mục hiện tại; cần xác nhận tham chiếu. Không cộng trùng các PAKN có nhiều dấu hiệu.'},
  {id:'5.4',numerator:'100% − (tỷ lệ hồ sơ quá hạn + tỷ lệ hồ sơ có PAKN hoặc dislike)',denominator:'',multiplier:'',target:90},
 ]},
];

// DOCX controls names, business rules, notes and data sources. Point ceilings
// remain independently sourced from captured API/METRICS, never inferred here.
export const formulaGroups:FormulaGroup[]=formulaDefinitions.map(group=>({
 ...group, items:group.items.map(formula=>{
  const document=formula.id==='3.5b'?{id:'3.5b',title:'Tỷ lệ TTHC có giao dịch thanh toán trực tuyến',group:'Thanh toán trực tuyến',business:['Số TTHC có giao dịch thanh toán trực tuyến / Tổng TTHC có yêu cầu nghĩa vụ tài chính (không trùng lặp) × 100%.','Tử số: totalDossierOnlineFormalityPaymentSuccess. Mẫu số: totalFeeDossierFormalityDistinct.','Tỷ lệ đạt từ 80% được 2 điểm; dưới 80% tính tỷ lệ / 80% × 2 điểm.'],notes:['Công thức đối chiếu từ API và biểu đồ Cổng DVCQG, được quản trị viên chấp thuận ngày 08/10/2026. Điểm tổng giữ theo nguồn.','Không tự quy đổi điểm khi thiếu dữ liệu hoặc mẫu số bằng 0.'],dataSources:['API formality-online-payment-tree và biểu đồ Thanh toán trực tuyến của Cổng DVCQG.']}:formulaDocument.records.find(row=>row.id===formula.id.replace(/[ab]$/,''));
  if(!document)throw new Error(`Missing formula document row: ${formula.id}`);
  let title=document.title;
  if(formula.id==='3.5')title='Tỷ lệ TTHC có yêu cầu nghĩa vụ tài chính được cung cấp trên Cổng DVCQG';
  if(formula.id==='3.6')title='Tỷ lệ hồ sơ thanh toán trực tuyến';
  if(formula.id==='4.5a')title=document.business.find(line=>line.startsWith('Tỷ lệ TTHC triển khai'))!.split(' = ')[0]!;
  if(formula.id==='4.5b')title=document.business.find(line=>line.startsWith('Tỷ lệ hồ sơ TTHC sử dụng'))!.split(' = ')[0]!;
  return {...formula,document,title,rules:document.business};
 })
}));

const esc=(v:string)=>v.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function referenceNotice(id:GroupId):string {
 const group=(activeConfiguration?.groups??formulaGroups).find(g=>g.id===id)!;
 return `<button type="button" class="formula-inline formula-link" data-formula-group="${id}">∑ Công thức và điều kiện nghiệp vụ · ${esc(group.name)} <span aria-hidden="true">→</span></button>`;
}
function sourceParagraphs(lines:string[]):string {
 if(!lines.length||lines.every(line=>!line.trim()||/^Chưa có thông tin/.test(line)))return '<p class="formula-missing">Chưa có thông tin</p>';
 return lines.filter(line=>line.trim()).map(line=>{
  if(/Update/i.test(line))return `<p class="formula-source-update">${esc(line.replace(/^=+|=+$/g,'').trim())}</p>`;
  const heading=/^(TH\d:|- TH\d:|- (Trả kết quả|Hiển thị kết quả|Tình huống sử dụng)|Cách tính:|Trong đó:|Tử số:|Mẫu số:|Danh sách trạng thái)/.test(line);
  const bullet=/^[-+]|^\([123]\)|^[a-gđ]\)/.test(line);
  return `<p class="${heading?'formula-business-heading':bullet?'formula-business-item':'formula-business-paragraph'}">${esc(line)}</p>`;
 }).join('');
}

function businessContent(f:Formula):string[] {
 if(f.businessLines)return f.businessLines;
 const business=f.document!.business;
 // 4.5 contains two independently scored ratios. Keep each scope with its own
 // card; the account/data flags in the first half also define the second ratio.
 const second=business.findIndex(line=>line.startsWith('Tỷ lệ hồ sơ TTHC sử dụng'));
 if(f.id==='4.5a')return business.slice(0,second);
 if(f.id==='4.5b')return [...business.slice(second),...business.filter(line=>line.includes('TaiKhoanDuocXacThucVoiVNeID')||line.includes('“taikhoanduocxacthucvoiVNeID”'))];
 return business;
}

function additionalEquations(f:Formula):string {
 const fraction=(label:string,numerator:string,denominator:string)=>extra({label,numerator,denominator});
 const extra=(e:FormulaExtra)=>{const op=e.operator??'divide',multiplier=e.multiplier??'× 100%';const expression=op==='divide'?`<span class="formula-fraction"><span>${esc(e.numerator)}</span><span>${esc(e.denominator)}</span></span>`:`<span class="formula-extra-expression">${multiplier?'(' : ''}<span>${esc(e.numerator)}</span><b>${({add:'+',subtract:'−',multiply:'×'} as const)[op]}</b><span>${esc(e.denominator)}</span>${multiplier?')' : ''}</span>`;return `<div class="formula-extra"><span class="formula-extra-label">Công thức phụ</span><div class="formula-equation"><span>${esc(e.label)} =</span>${expression}${multiplier?`<span>${esc(multiplier)}</span>`:''}</div></div>`;};
 if(f.extras)return f.extras.map(extra).join('');
 if(f.id==='3.1')return fraction('Tỷ lệ toàn trình','TTHC cung cấp DVCTT toàn trình','TTHC đủ điều kiện thực hiện DVCTT toàn trình')+fraction('Tỷ lệ một phần','TTHC cung cấp DVCTT một phần','TTHC thuộc thẩm quyền giải quyết');
 if(f.id==='3.3')return fraction('Tỷ lệ trực tiếp','Hồ sơ tiếp nhận trong kỳ có kênh 1 hoặc thiếu kênh','Tổng hồ sơ tiếp nhận trong kỳ')+fraction('Tỷ lệ bưu chính','Hồ sơ tiếp nhận trong kỳ có kênh 3','Tổng hồ sơ tiếp nhận trong kỳ');
 return '';
}

function accordion(kind:string,label:string,body:string,expanded=false):string {
 const mark=kind==='notes'?'warning':kind==='calculation'?'chart':'document';
 return `<details class="formula-accordion formula-accordion-${kind}"${expanded?' open':''}><summary><span class="formula-accordion-icon" aria-hidden="true">${icon(mark)}</span><span>${label}</span><span class="formula-chevron" aria-hidden="true">⌄</span></summary><div class="formula-accordion-body">${body}</div></details>`;
}

// Keep persisted identifiers stable so historical and authored configurations
// are unchanged; only the visible reference number is renamed.
export function formulaDisplayCode(id:string):string {
 return id==='3.5'?'3.5a':id;
}
export function formulaCard(group:GroupId,f:Formula):string {
 const maximum=f.maximum!==undefined?f.maximum:formulaMaximums[group].find(row=>row.formulaId===f.id)?.maximum??null;
 const maximumLabel=f.id==='5.1'?'Chỉ tiêu tham khảo · Không chấm điểm':maximumText(maximum);
 const equationLabel=f.equationLabel??(f.id==='2.2'?'Thời gian trung bình':f.id==='3.3'?'Tỷ lệ trực tuyến':'Tỷ lệ');
 const clarification=f.clarification??(f.id==='2.1'?'Tài liệu mô tả cách xác định tỷ lệ đúng hạn; chưa nêu phép quy đổi điểm riêng. Điểm tối đa 20 được giữ theo dữ liệu đã xác định, không suy ra công thức chấm điểm từ mức điểm tối đa.':f.id==='3.5'||f.id==='4.4'?undefined:f.caution);
 const scoring=f.id==='5.1'?'':f.target?`<div class="formula-score-equation" aria-label="Công thức quy đổi điểm"><span>Điểm =</span><span class="formula-score-cases"><span><i>P</i><sub>max</sub><small>nếu <i>R</i> ≥ ${f.target}%</small></span><span><span class="formula-fraction"><span><i>R</i> × <i>P</i><sub>max</sub></span><span>${f.target}%</span></span><small>nếu <i>R</i> &lt; ${f.target}%</small></span></span></div><p class="formula-symbols"><i>R</i>: tỷ lệ của chỉ tiêu; <i>P</i><sub>max</sub>: điểm tối đa riêng.${maximum===null?' Điểm tối đa riêng: Chưa xác định.':''}</p>`:maximum!==null&&maximum>0?`<div class="formula-score-equation" data-score-mode="linear" aria-label="Công thức quy đổi điểm"><span>Điểm =</span><span class="formula-fraction"><span><i>R</i> × <i>P</i><sub>max</sub></span><span>100%</span></span></div><p class="formula-symbols"><i>R</i>: tỷ lệ (%) của chỉ tiêu; <i>P</i><sub>max</sub>: điểm tối đa riêng. Không áp dụng ngưỡng đạt điểm.</p>`:'';
 const heading=f.businessHeading??(f.id.startsWith('4.5')?'Mục 4.5: '+f.document.title:'');
 const versionNote=f.versionNote??(f.id==='3.2'?'Biểu thức trên theo phần Update; mô tả trước cập nhật được giữ bên dưới để đối chiếu.':'');
 const mathNote=f.mathNote??(f.id==='5.2'?'Dòng công thức trong tài liệu bị lỗi văn bản. Biểu thức dưới đây diễn giải từ quy tắc nghiệp vụ; chưa xác nhận phép quy đổi điểm.':'');
 const symbols=f.symbols??(f.id==='3.3'?'Hệ số đồng bộ = tỷ lệ đồng bộ (%) / 100. Ví dụ: 80% → 0,8.':'');
 const business=`${scoring}<section class="formula-business"><h4>Mô tả nghiệp vụ</h4>${heading?`<p class="formula-business-heading">${esc(heading)}</p>`:''}${versionNote?`<p class="formula-version-note">${esc(versionNote)}</p>`:''}${sourceParagraphs(businessContent(f))}</section>`;
 const notes=sourceParagraphs(f.document.notes)+(clarification?`<div class="formula-clarification"><strong>Cần đối chiếu</strong><p>${esc(clarification)}</p></div>`:'');
 return `<article class="formula-card" data-formula-id="${f.id}"><div class="formula-card-heading"><span class="formula-code">${formulaDisplayCode(f.id)}</span><h3>${esc(f.title)}</h3><div class="formula-card-meta"><span class="maximum-badge ${maximum===null?'unresolved':''}">${f.id==='5.1'?'':'Điểm tối đa: '}${maximumLabel}</span>${f.id!=='5.1'&&f.target?`<span class="badge good">Ngưỡng đạt: ${f.target}%</span>`:''}</div></div>
 <section class="formula-math-section" aria-label="Công thức toán học">${mathNote?`<p class="formula-version-note">${esc(mathNote)}</p>`:''}<div class="formula-equation"><span>${esc(equationLabel)} =</span>${f.denominator?`<span class="formula-fraction"><span>${esc(f.numerator)}</span><span>${esc(f.denominator)}</span></span>`:`<strong>${esc(f.numerator)}</strong>`}<span>${esc(f.multiplier??'× 100%')}</span></div>${symbols?`<p class="formula-symbols">${esc(symbols)}</p>`:''}${additionalEquations(f)}</section>
 <div class="formula-accordions">${accordion('calculation','Nghiệp vụ và cách tính',business)}${accordion('sources','Nguồn dữ liệu',sourceParagraphs(f.document.dataSources))}${accordion('notes','Lưu ý khi đánh giá',notes)}</div></article>`;
}
export function displayedFormulas(group:FormulaGroup):Formula[]{
 // Classification is displayed for reference only, never used to score the group.
 return group.items;
}
export function defaultFormulaConfiguration():FormulaConfiguration {
 return {source:{...formulaSource},guide:['Nguồn: '+formulaSource.name+' và bảng METRICS trong Công thức 766.xlsx do quản trị viên cung cấp.','Tỷ lệ: tử số / mẫu số × 100%; riêng 3.3 nhân thêm hệ số đồng bộ.','Quy đổi điểm: chỉ áp dụng ngưỡng và điểm tối đa khi đã xác định. Mức điểm tối đa không đồng nghĩa công thức quy đổi đã được xác nhận.','Thiếu dữ liệu: không phải số 0. Mức điểm chưa rõ ghi “Chưa xác định”; điểm nguồn được giữ nguyên.'],groups:formulaGroups.map(g=>({...g,items:g.items.map(f=>({...f,
 target:f.target??null,multiplier:f.multiplier??'× 100%',caution:f.caution??'',
 maximum:formulaMaximums[g.id].find(row=>row.formulaId===f.id)?.maximum??null,
 equationLabel:f.id==='2.2'?'Thời gian trung bình':f.id==='3.3'?'Tỷ lệ trực tuyến':'Tỷ lệ',
 businessLines:businessContent(f),businessHeading:f.id.startsWith('4.5')?'Mục 4.5: '+f.document.title:'',
 versionNote:f.id==='3.2'?'Biểu thức trên theo phần Update; mô tả trước cập nhật được giữ bên dưới để đối chiếu.':'',
 mathNote:f.id==='5.2'?'Dòng công thức trong tài liệu bị lỗi văn bản. Biểu thức dưới đây diễn giải từ quy tắc nghiệp vụ; chưa xác nhận phép quy đổi điểm.':'',
 symbols:f.id==='3.3'?'Hệ số đồng bộ = tỷ lệ đồng bộ (%) / 100. Ví dụ: 80% → 0,8.':'',
 clarification:f.id==='2.1'?'Tài liệu mô tả cách xác định tỷ lệ đúng hạn; chưa nêu phép quy đổi điểm riêng. Điểm tối đa 20 được giữ theo dữ liệu đã xác định, không suy ra công thức chấm điểm từ mức điểm tối đa.':f.id==='3.5'||f.id==='4.4'?'':f.caution??'',
 extras:f.id==='3.1'?[{label:'Tỷ lệ toàn trình',numerator:'TTHC cung cấp DVCTT toàn trình',denominator:'TTHC đủ điều kiện thực hiện DVCTT toàn trình'},{label:'Tỷ lệ một phần',numerator:'TTHC cung cấp DVCTT một phần',denominator:'TTHC thuộc thẩm quyền giải quyết'}]:f.id==='3.3'?[{label:'Tỷ lệ trực tiếp',numerator:'Hồ sơ tiếp nhận trong kỳ có kênh 1 hoặc thiếu kênh',denominator:'Tổng hồ sơ tiếp nhận trong kỳ'},{label:'Tỷ lệ bưu chính',numerator:'Hồ sơ tiếp nhận trong kỳ có kênh 3',denominator:'Tổng hồ sơ tiếp nhận trong kỳ'}]:[]
 }))}))};
}
export function renderFormulaReference(selected:GroupId='transparency',configuration:FormulaConfiguration|null=activeConfiguration):string {
 const formulaGroups=configuration?.groups??defaultFormulaConfiguration().groups;
 return `<section class="formula-page"><header class="bento-heading"><h1>Công thức tính Bộ chỉ số 766</h1></header>
 <nav class="formula-index" aria-label="Danh mục nhóm công thức">${formulaGroups.map(g=>`<button type="button" data-formula-group="${g.id}" aria-label="${esc(g.name)}, tối đa ${g.maximum} điểm" aria-pressed="${g.id===selected}" style="--formula-color:${groupColors[g.id]}">${groupIcon(g.id)}<span class="formula-group-name">${esc(g.name)}</span><strong class="formula-group-maximum" aria-hidden="true">${g.maximum}</strong></button>`).join('')}</nav>
 ${formulaGroups.filter(g=>g.id===selected).map(g=>`<section class="formula-group" id="formula-${g.id}" style="--formula-color:${groupColors[g.id]}"><header><span class="bento-icon">${groupIcon(g.id)}</span><h2>${esc(g.name)}</h2></header>${displayedFormulas(g).map(f=>formulaCard(g.id,f)).join('')}</section>`).join('')}</section>`;
}
