"""Bounded XLSX import. No formula evaluation, macros or external resources."""
import base64
import binascii
import io
import re
import unicodedata
import zipfile
from xml.etree import ElementTree as ET

HEADERS=['Câu hỏi','Đáp án A','Đáp án B','Đáp án C','Đáp án D','Đáp án E','Đáp án F','Đáp án đúng','Giải thích']
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
MAX_FILE=2*1024*1024

def question_key(prompt):
    return ' '.join(unicodedata.normalize('NFC',prompt).casefold().split())

def read_questions(encoded,validate):
    try:
        data=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error):
        raise ValueError('Nội dung file không hợp lệ.') from None
    if not data or len(data)>MAX_FILE:raise ValueError('File Excel tối đa 2 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries=archive.infolist();names=[e.filename for e in entries]
            if len(entries)>1000 or len(set(names))!=len(names) or sum(e.file_size for e in entries)>8*1024*1024:
                raise ValueError('File Excel vượt giới hạn giải nén.')
            if any(e.flag_bits&1 for e in entries) or any('vbaproject' in n.lower() for n in names):
                raise ValueError('Không hỗ trợ file có mật khẩu hoặc macro.')
            def xml(name):
                raw=archive.read(name)
                decoded=raw.decode('utf-8-sig')
                if '\x00' in decoded or '<!DOCTYPE' in decoded.upper() or '<!ENTITY' in decoded.upper():raise ValueError('XML không an toàn.')
                return ET.fromstring(decoded)
            workbook=xml('xl/workbook.xml')
            sheet=next((s for s in workbook.findall('s:sheets/s:sheet',NS) if s.get('name')=='CauHoi'),None)
            if sheet is None:raise ValueError('Thiếu sheet CauHoi. Hãy sử dụng file mẫu.')
            rid=sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            rels=xml('xl/_rels/workbook.xml.rels')
            rel=next((r for r in rels if r.get('Id')==rid),None)
            if rel is None or rel.get('TargetMode')=='External':raise ValueError('Sheet không hợp lệ.')
            target=rel.get('Target','').lstrip('/')
            path=target if target.startswith('xl/') else 'xl/'+target
            if not re.fullmatch(r'xl/worksheets/[^/]+\.xml',path):raise ValueError('Đường dẫn sheet không hợp lệ.')
            strings=[]
            if 'xl/sharedStrings.xml' in names:
                strings=[''.join(t.text or '' for t in n.findall('.//s:t',NS)) for n in xml('xl/sharedStrings.xml').findall('s:si',NS)]
            rows=[];errors=[]
            for row in xml(path).findall('s:sheetData/s:row',NS):
                cells=['']*9;number=int(row.get('r','0'));seen=set()
                if number<1 or number>501:raise ValueError('Tối đa 500 câu hỏi; không để dòng dữ liệu ngoài dòng 501.')
                for cell in row.findall('s:c',NS):
                    address=cell.get('r','');match=re.fullmatch(r'([A-Z]+)([0-9]+)',address)
                    if not match or int(match[2])!=number or address in seen:raise ValueError('Địa chỉ ô không hợp lệ.')
                    seen.add(address);col=match[1]
                    if cell.find('s:f',NS) is not None:errors.append({'row':number,'message':'Không nhập công thức Excel trong bảng câu hỏi.'});continue
                    v=cell.find('s:v',NS);value=v.text or '' if v is not None else ''
                    kind=cell.get('t')
                    if kind=='s':
                        index=int(value)
                        if index<0:raise ValueError('Chỉ mục chuỗi không hợp lệ.')
                        value=strings[index]
                    elif kind=='inlineStr':value=''.join(t.text or '' for t in cell.findall('s:is//s:t',NS))
                    elif kind in ('e','b'):errors.append({'row':number,'message':'Ô lỗi hoặc giá trị logic không được hỗ trợ.'})
                    if col not in list('ABCDEFGHI'):
                        if value.strip():errors.append({'row':number,'message':'Dữ liệu ngoài 9 cột của file mẫu.'})
                    else:cells[ord(col)-65]=value.strip()
                rows.append((number,cells))
            if len(rows)>501 or len({n for n,_ in rows})!=len(rows):raise ValueError('Số dòng hoặc dòng lặp không hợp lệ.')
            if next((cells for n,cells in rows if n==1),None)!=HEADERS:raise ValueError('Tên và thứ tự cột không đúng file mẫu.')
            questions=[]
            for number,cells in rows:
                if number==1 or not any(cells):continue
                try:
                    choices=cells[1:7]
                    while choices and not choices[-1]:choices.pop()
                    answer=cells[7].upper()
                    if answer not in 'ABCDEF' or len(answer)!=1:raise ValueError('Đáp án đúng phải là A, B, C, D, E hoặc F.')
                    q=validate(prompt=cells[0],choices=choices,correctIndex=ord(answer)-65,explanation=cells[8])
                    questions.append((number,q))
                except ValueError:
                    errors.append({'row':number,'message':'Kiểm tra câu hỏi (5–1000 ký tự), 2–6 đáp án liên tục (mỗi đáp án tối đa 400 ký tự, không trùng), đáp án đúng A–F và giải thích tối đa 2000 ký tự.'})
            if not questions and not errors:raise ValueError('File chưa có câu hỏi.')
            return questions,errors
    except (zipfile.BadZipFile,KeyError,IndexError,ET.ParseError,UnicodeError,OverflowError,RuntimeError,NotImplementedError):
        raise ValueError('File không phải Excel .xlsx hợp lệ hoặc đã hỏng.') from None
