import unittest, uuid
from copy import deepcopy
from test_trivia import TriviaTests
from qd766.backend.formula_configuration import SEED
from qd766.backend.models import FormulaConfigRevision,FormulaConfigHead,Department,UserAccount

ADMIN='/api/v1/admin/formula-configuration'
class FormulaConfigurationTests(unittest.TestCase):
    def test_authorized_deployment_import_preserves_history_and_rejects_overwrite(self):
        import importlib.util
        from pathlib import Path
        from datetime import datetime, timezone
        from qd766.backend.models import AdminAudit
        from sqlalchemy import select
        path=Path(__file__).resolve().parents[1]/'tools/migrate_formula_configuration.py'
        spec=importlib.util.spec_from_file_location('formula_import',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        draft=deepcopy(SEED);draft['groups'][0]['items'][0]['businessLines']=['Nội dung quản trị đã lưu']
        with self.fixture.app.state.session_factory.begin() as db:
            db.add(FormulaConfigRevision(version=1,content=deepcopy(SEED),note='Bản gốc',created_at=datetime.now(timezone.utc)))
            db.flush();db.add(FormulaConfigHead(id=1,version=1));db.flush()
            self.assertEqual(module.import_saved(db,draft,'a'*64),2)
        with self.fixture.app.state.session_factory.begin() as db:
            self.assertEqual(db.get(FormulaConfigRevision,1).content,SEED)
            self.assertEqual(db.get(FormulaConfigRevision,2).content,draft)
            self.assertEqual(module.import_saved(db,draft,'a'*64),2)
            self.assertEqual(db.get(UserAccount,self.fixture.ids['owner']).credit_balance,123)
            audit_row=db.scalar(select(AdminAudit).where(AdminAudit.action=='formula_configuration_saved'))
            self.assertEqual(audit_row.details['snapshot_sha256'],'a'*64)
            with self.assertRaisesRegex(RuntimeError,'EXISTING_PRODUCTION_EDITS'):
                module.import_saved(db,SEED,'b'*64)
    def test_payment_upgrade_preserves_authored_text_and_other_groups(self):
        from qd766.backend.formula_configuration import upgrade_payment_content, validate_content
        old=deepcopy(SEED)
        payment=next(g for g in old['groups'] if g['id']=='formality-online-payment-tree')
        payment['items']=[i for i in payment['items'] if i['id']!='3.5b']
        payment['items'][0]['businessLines']=['Nghiệp vụ do quản trị viên vừa nhập']
        payment['items'][1]['maximum']=10
        upgraded=upgrade_payment_content(old)
        validate_content(upgraded)
        result=next(g for g in upgraded['groups'] if g['id']==payment['id'])
        self.assertEqual([i['maximum'] for i in result['items']],[2,2,6])
        self.assertEqual(result['items'][0]['businessLines'],payment['items'][0]['businessLines'])
        self.assertEqual([g for g in old['groups'] if g['id']!=payment['id']], [g for g in upgraded['groups'] if g['id']!=payment['id']])
        self.assertEqual(len(payment['items']),2)
        result['items'][0]['businessLines']=['Chỉnh sửa sau nâng cấp']
        self.assertEqual(upgrade_payment_content(upgraded),upgraded)
    def setUp(self):
        self.fixture=TriviaTests();self.fixture.setUp();self.client=self.fixture.client
        with self.fixture.app.state.session_factory.begin() as db:
            root=uuid.uuid4();db.add(Department(id=root,name='Tỉnh mẫu'));db.flush()
            db.get(UserAccount,self.fixture.ids['agency']).root_department_id=root
    def tearDown(self):self.fixture.tearDown()
    def test_migration_seeds_original_revision(self):
        import importlib.util
        from pathlib import Path
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        engine=self.fixture.app.state.engine
        FormulaConfigHead.__table__.drop(engine);FormulaConfigRevision.__table__.drop(engine)
        path=Path(__file__).resolve().parents[1]/'alembic/versions/20261008_0024_formula_configuration.py'
        spec=importlib.util.spec_from_file_location('formula_migration',path)
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):migration.upgrade()
        value=self.client.get(ADMIN).json();self.assertEqual(value['activeVersion'],1)
        self.assertEqual(value['configuration'],SEED);self.assertEqual(value['history'][0]['actor'],'Bản gốc')
    def test_seed_and_save_without_other_group_changes(self):
        old=self.client.get(ADMIN).json();self.assertEqual(old['configuration'],SEED)
        draft=deepcopy(SEED);draft['groups'][0]['items'][0]['title']='Tên được cập nhật'
        result=self.client.post(ADMIN,json=dict(expectedVersion=0,configuration=draft,note='Cập nhật tên'),headers=self.fixture.headers)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['version'],1)
        self.assertEqual(self.client.get(ADMIN).json()['configuration'],draft)
        self.assertEqual(self.client.get(ADMIN+'?version=0').json()['configuration'],SEED)
        self.fixture.login('agency')
        read=self.client.get('/api/v1/formula-reference');self.assertEqual(read.status_code,200,read.text)
        self.assertEqual(read.json()['configuration'],draft);self.assertEqual(read.headers['cache-control'],'no-store')
        self.assertNotIn('actor',read.text)
    def test_conflict_and_revision_history(self):
        for version in range(2):
            draft=deepcopy(SEED);draft['groups'][0]['name']=f'Nhóm {version}'
            response=self.client.post(ADMIN,json=dict(expectedVersion=version,configuration=draft,note='Sửa tên nhóm'),headers=self.fixture.headers)
            self.assertEqual(response.status_code,200,response.text)
        stale=self.client.post(ADMIN,json=dict(expectedVersion=0,configuration=SEED,note='Ghi đè'),headers=self.fixture.headers)
        self.assertEqual(stale.status_code,409)
        self.assertEqual(len(self.client.get(ADMIN).json()['history']),2)
        self.assertEqual(self.client.get(ADMIN+'?version=1').json()['configuration']['groups'][0]['name'],'Nhóm 0')
    def test_extra_operators_preserve_content_and_validate(self):
        for version,operator in enumerate(('add','subtract','multiply','divide')):
            draft=deepcopy(SEED)
            draft['groups'][0]['items'][0]['extras']=[dict(label='Phụ',numerator='A',denominator='B',operator=operator,multiplier='')]
            result=self.client.post(ADMIN,json=dict(expectedVersion=version,configuration=draft,note='Thêm phép tính phụ'),headers=self.fixture.headers)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(self.client.get(ADMIN).json()['configuration'],draft)
        draft['groups'][0]['items'][0]['extras'][0]['operator']='execute'
        result=self.client.post(ADMIN,json=dict(expectedVersion=4,configuration=draft,note='Invalid operator'),headers=self.fixture.headers)
        self.assertEqual(result.status_code,422)
    def test_admin_csrf_and_no_credit_change(self):
        payload=dict(expectedVersion=0,configuration=SEED,note='Ghi chú')
        self.assertEqual(self.client.post(ADMIN,json=payload).status_code,403)
        self.fixture.login('agency');self.assertEqual(self.client.get(ADMIN).status_code,403)
        self.assertEqual(self.client.post(ADMIN,json=payload,headers=self.fixture.headers).status_code,403)
        self.fixture.login(None);self.assertEqual(self.client.get('/api/v1/formula-reference').status_code,401)
        with self.fixture.app.state.session_factory() as db:
            self.assertEqual(db.get(UserAccount,self.fixture.ids['owner']).credit_balance,123)
    def test_validation_and_missing_schema_preserve_reference(self):
        for mutate in (lambda c:c['groups'].pop(),lambda c:c['groups'].__setitem__(0,'bad'),
                       lambda c:c['groups'][0]['items'][0].__setitem__('maximum',-1),
                       lambda c:c['groups'][0]['items'][0].__setitem__('target',0),
                       lambda c:c.__setitem__('source',[])):
            draft=deepcopy(SEED);mutate(draft)
            response=self.client.post(ADMIN,json=dict(expectedVersion=0,configuration=draft,note='Invalid'),headers=self.fixture.headers)
            self.assertEqual(response.status_code,422,response.text)
        engine=self.fixture.app.state.engine
        FormulaConfigHead.__table__.drop(engine);FormulaConfigRevision.__table__.drop(engine)
        value=self.client.get(ADMIN).json();self.assertFalse(value['schemaReady']);self.assertEqual(value['configuration'],SEED)
        self.assertEqual(self.client.post(ADMIN,json=dict(expectedVersion=0,configuration=SEED,note='Save'),headers=self.fixture.headers).status_code,503)

if __name__=='__main__':unittest.main()
