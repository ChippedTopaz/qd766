import type {Workbook} from "exceljs";
import {analysisExcelFilename} from './excel-export.js';
import type {Snapshot} from './types.js';

export interface VisibleComparison {title:string;headers:string[];rows:string[][]}
export interface ComparisonContext {organization:string;period:string;scope:string;updated:string;snapshot?:Snapshot}
const integerFormat='#,##0';
export function displayedNumber(text:string):{value:number;format:string}|null {
  const value=text.trim();
  if(!/^[+-]?\d+(?:\.\d{3})*(?:,\d+)?%?$/.test(value))return null;
  const percent=value.endsWith('%');
  const numeric=Number(value.replace(/\./g,'').replace(',','.').replace('%',''));
  if(!Number.isFinite(numeric))return null;
  const decimals=value.includes(',')?value.split(',')[1]!.replace('%','').length:0;
  return {value:percent?numeric/100:numeric,format:percent?'0'+(decimals?'.'+'0'.repeat(decimals):'')+'%':integerFormat+(decimals?'.'+'0'.repeat(decimals):'')};
}

export function buildComparisonWorkbook(WorkbookClass:new()=>Workbook,comparison:VisibleComparison,context:ComparisonContext):Workbook {
  const workbook=new WorkbookClass();
  const sheet=workbook.addWorksheet('So sánh');
  sheet.addRow([comparison.title]);
  sheet.addRow([context.organization,context.period,context.scope]);
  sheet.addRow([context.updated]);
  const header=sheet.addRow(comparison.headers);
  header.eachCell(cell=>{cell.font={bold:true,color:{argb:'FFFFFFFF'}};cell.fill={type:'pattern',pattern:'solid',fgColor:{argb:'FF4338CA'}};});
  for(const values of comparison.rows){
    const row=sheet.addRow(values.map(value=>displayedNumber(value)?.value??value));
    row.eachCell((cell,index)=>{
      const number=displayedNumber(values[index-1]??'');
      if(number){
        cell.numFmt=(values[index-1]??'').startsWith('+')?'+'+number.format+';'+number.format+';'+number.format:number.format;
        cell.alignment={horizontal:'right'};
        if(/Tăng|giảm|Chênh lệch/.test(comparison.headers[index-1]??''))cell.font={color:{argb:number.value>0?'FF059669':number.value<0?'FFDC2626':'FF64748B'}};
      }
    });
  }
  sheet.eachRow(row=>{row.height=15;});
  sheet.getRow(1).font={bold:true,size:12,color:{argb:'FF172554'}};
  sheet.columns.forEach((column,index)=>{
    column.width=Math.max(10,...[comparison.headers,...comparison.rows].map(row=>(row[index]??'').length+3));
  });
  if(comparison.headers.length){
    sheet.autoFilter={from:{row:4,column:1},to:{row:4,column:comparison.headers.length}};
  }
  sheet.views=[{state:'frozen',ySplit:4}];
  return workbook;
}

export function readVisibleTable(table:HTMLTableElement,title:string):VisibleComparison {
  const headers=Array.from(table.querySelectorAll('thead th')).map(cell=>cell.textContent?.trim()??'');
  const rows=Array.from(table.querySelectorAll<HTMLTableRowElement>('tbody tr,tfoot tr')).filter(row=>!row.hidden).map(row=>{
    const values:string[]=[];
    for(const cell of Array.from(row.cells)){
      values.push(cell.textContent?.trim()??'');
      for(let i=1;i<cell.colSpan;i++)values.push('');
    }
    return values;
  });
  return {title,headers,rows};
}

export function bindComparisonExports(context:ComparisonContext,WorkbookClass:()=>new()=>Workbook):void {
  const download=async(button:HTMLButtonElement,comparison:VisibleComparison)=>{
    button.disabled=true;
    try{
      const workbook=buildComparisonWorkbook(WorkbookClass(),comparison,context);
      const buffer=await workbook.xlsx.writeBuffer();
      const url=URL.createObjectURL(new Blob([buffer as BlobPart],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}));
      try{
        const link=document.createElement('a');link.href=url;
        const slug=(value:string)=>value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[đĐ]/g,'d').replace(/[^a-zA-Z0-9]+/g,'-').replace(/^-|-$/g,'');
        const timestamp=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date()).replace(/[^0-9]/g,'');
        link.download=context.snapshot?analysisExcelFilename(context.organization,context.snapshot,'scores'):`${slug(context.organization)}-chua-ro-ngay-cap-nhat-tonghop-${timestamp}.xlsx`;
        document.body.append(link);link.click();link.remove();
      }finally{window.setTimeout(()=>URL.revokeObjectURL(url),1000);}
    }catch{window.alert('Không tạo được file Excel. Vui lòng thử lại.');}
    finally{button.disabled=false;}
  };
  const addButton=(host:Element,read:()=>VisibleComparison)=>{
    if(host.querySelector('[data-comparison-export]'))return;
    const button=document.createElement('button');button.className='btn small comparison-export';button.textContent='Tải Excel';
    button.setAttribute('data-comparison-export','');
    button.addEventListener('click',()=>void download(button,read()));
    if(host.matches('.comparison-card'))host.querySelector('h3')?.after(button);else host.append(button);
  };
  // Export rendered rows only: respects filtering and the caller's access scope.
  document.querySelectorAll<HTMLTableElement>('.content table').forEach(table=>{
    if(table.matches('.metric-table,.progress-table,.leadership-table'))return;
    const panel=table.closest('.panel');const host=panel?.querySelector('.panel-head');
    if(!host)return;
    const title=host.querySelector('h2,h3')?.textContent?.trim()??'Bảng so sánh';
    addButton(host,()=>readVisibleTable(table,title));
  });
  document.querySelectorAll<HTMLElement>('.content .comparison-card').forEach(card=>{
    if(!card.querySelector('.peer-row'))return;
    const title=card.querySelector('h3')?.textContent?.trim()??'So sánh cùng cấp';
    addButton(card,()=>({title,headers:['Cơ quan, đơn vị','Điểm','Hạng'],rows:Array.from(card.querySelectorAll('.peer-row')).map(row=>Array.from(row.children).map(cell=>cell.textContent?.trim()??''))}));
  });
  document.querySelectorAll<HTMLElement>('.content .split>.panel,.content .peer-grid>.panel').forEach(panel=>{
    const peers=panel.querySelectorAll('.peer-row');if(!peers.length)return;
    const head=panel.querySelector('.panel-head');if(!head)return;
    const title=head.querySelector('h2')?.textContent?.trim()??'So sánh';
    addButton(head,()=>({title,headers:['Cơ quan, đơn vị','Điểm',title.includes('Quy mô')?'Số hồ sơ':'Chênh lệch'],rows:Array.from(peers).map(row=>Array.from(row.children).map(cell=>cell.textContent?.trim()??''))}));
  });
}
