import base64,io,zipfile,unittest
from pathlib import Path
from xml.sax.saxutils import escape
from sqlalchemy import select,func
import test_trivia
from qd766.backend.trivia_import import HEADERS,read_questions
from qd766.backend.trivia import QuestionInput
from qd766.backend.models import TriviaQuestion,UserAccount,TriviaAnswer

def xlsx(rows,extra=None):
    xml='<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    for n,cells in enumerate([HEADERS,*rows],1):
        xml+=f'<row r="{n}">'+''.join(f'<c r="{chr(65+i)}{n}" t="inlineStr"><is><t>{escape(v)}</t></is></c>' for i,v in enumerate(cells))+'</row>'
    xml+='</sheetData></worksheet>'
    files={'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="CauHoi" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels':'<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml':xml}
    files.update(extra or {})
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    return base64.b64encode(buf.getvalue()).decode()

ROW=['Câu hỏi nhập mới bằng Excel?','Đúng','Sai','','','','','A','Giải thích mẫu']

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_trivia.TriviaTests();self.fixture.setUp();self.client=self.fixture.client
    def tearDown(self):self.fixture.tearDown()
    def post(self,file,confirm=False,headers=None):
        return self.client.post('/api/v1/admin/trivia/import',json={'file':file,'confirm':confirm},headers=self.fixture.headers if headers is None else headers)
    def count(self):
        with self.fixture.app.state.session_factory() as db:return db.scalar(select(func.count()).select_from(TriviaQuestion))
    def test_preview_atomic_save_repeat_and_no_credit_or_game_changes(self):
        file=xlsx([ROW,ROW,['Câu hỏi thứ hai nhập Excel?',*ROW[1:]]])
        preview=self.post(file);self.assertEqual(preview.status_code,200,preview.text);r=preview.json()
        self.assertEqual(r['newCount'],2);self.assertEqual(len(r['duplicates']),1);self.assertEqual(self.count(),0)
        self.assertEqual(self.post(file,True).json()['saved'],2);self.assertEqual(self.count(),2)
        self.assertEqual(self.post(file,True).json()['saved'],0);self.assertEqual(self.count(),2)
        with self.fixture.app.state.session_factory() as db:
            self.assertTrue(all(q.state=='draft' and not q.locked for q in db.scalars(select(TriviaQuestion))))
            self.assertTrue(all(u.credit_balance==123 for u in db.scalars(select(UserAccount))))
            self.assertEqual(db.scalar(select(func.count()).select_from(TriviaAnswer)),0)
    def test_errors_block_entire_file_and_report_excel_line(self):
        bad=ROW.copy();bad[7]='F';file=xlsx([ROW,bad])
        report=self.post(file).json();self.assertFalse(report['valid']);self.assertEqual(report['errors'][0]['row'],3)
        self.assertEqual(self.post(file,True).status_code,422);self.assertEqual(self.count(),0)
    def test_case_whitespace_duplicate_never_overwrites_published(self):
        q=self.fixture.create(prompt=ROW[0]);row=ROW.copy();row[0]='  CÂU HỎI  NHẬP MỚI BẰNG EXCEL? ';row[7]='B'
        self.assertEqual(self.post(xlsx([row]),True).json()['saved'],0)
        with self.fixture.app.state.session_factory() as db:
            found=db.scalar(select(TriviaQuestion));self.assertEqual(found.correct_index,0);self.assertTrue(found.locked)
    def test_admin_csrf_required(self):
        file=xlsx([ROW]);self.assertEqual(self.post(file,headers={}).status_code,403)
        for token in ('agency','pending','locked',None):
            self.fixture.login(token);self.assertIn(self.post(file,True).status_code,(401,403))
        self.assertEqual(self.count(),0)
    def test_bad_structure_formula_entity_macro_size_and_rows(self):
        badsheet='<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>'
        variants=['bad base64',base64.b64encode(b'notzip').decode(),xlsx([ROW],{'xl/worksheets/sheet1.xml':badsheet}),xlsx([ROW],{'xl/vbaProject.bin':'macro'}),xlsx([ROW],{'xl/workbook.xml':'<!DOCTYPE x [<!ENTITY a "test">]><x>&a;</x>'}),xlsx([ROW]*501),base64.b64encode(b'x'*(2*1024*1024+1)).decode(),xlsx([ROW],{'huge':'x'*(8*1024*1024)})]
        for file in variants:
            with self.subTest(length=len(file)):self.assertEqual(self.post(file,True).status_code,422)
        self.assertEqual(self.count(),0)
        r=self.client.post('/api/v1/admin/trivia/import',content=b'x'*(3*1024*1024+1),headers=self.fixture.headers);self.assertEqual(r.status_code,413)
    def test_template_is_compatible_and_has_example(self):
        data=(Path(__file__).resolve().parents[1]/'web/assets/trivia-question-template.xlsx').read_bytes()
        questions,errors=read_questions(base64.b64encode(data).decode(),QuestionInput)
        self.assertEqual(errors,[]);self.assertEqual(len(questions),1);self.assertEqual(questions[0][1].correctIndex,0)
    def test_empty_choices_gap_duplicates_and_answer_validation(self):
        variants=[]
        for index,value in ((1,''),(2,'Đúng'),(7,'AB'),(7,'1'),(0,'abc'),(8,'x'*2001)):
            row=ROW.copy();row[index]=value;variants.append(row)
        report=self.post(xlsx(variants)).json();self.assertFalse(report['valid']);self.assertEqual(len(report['errors']),len(variants))

if __name__=='__main__':unittest.main()
