import uuid
import unittest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from fastapi.testclient import TestClient
import test_trial_admin
from qd766.backend.models import SystemNotice, SystemNoticeDismissal, AdminAudit, UserAccount, LoginSession, CreditLedgerEntry, CollectionJob
from qd766.backend.auth import digest


class SystemNoticeTests(unittest.TestCase):
    def setUp(self):
        self.f=test_trial_admin.TrialAdminTests();self.f.setUp()
        self.admin=self.f.client
        self.user=TestClient(self.f.app,base_url='https://testserver')
        with self.f.app.state.session_factory.begin() as db:
            account=UserAccount(external_subject='notice-viewer',display_name='Viewer',email='viewer@example.test',role='user',trial_admitted=True)
            db.add(account);db.flush();self.user_id=account.id
            db.add(LoginSession(token_hash=digest('notice-user'),account_id=account.id,csrf_token='user-csrf',expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        self.user.cookies.set('qd766_session','notice-user')
        self.base='/api/v1/admin/system-notices'
        self.public='/api/v1/me/system-notices'

    def tearDown(self):
        self.user.close();self.f.tearDown()

    def draft(self,**kwargs):
        body={'id':str(uuid.uuid4()),'title':'Cập nhật dữ liệu','summary':'Thông tin quan trọng','body':'Đoạn 1\nĐoạn 2','kind':'important','expectedRevision':0,**kwargs}
        r=self.admin.post(self.base,json=body,headers=self.f.headers)
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def action(self,n,action='publish'):
        r=self.admin.post(self.base+'/'+n['id']+'/action',json={'action':action,'expectedRevision':n['revision']},headers=self.f.headers)
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def test_draft_preview_publish_history_and_stop_popup(self):
        n=self.draft(title="<script>alert(1)</script> ' OR 1=1")
        self.assertEqual(self.user.get(self.public).json()['items'],[])
        self.assertEqual(self.user.get(self.public+'/'+n['id']).status_code,404)
        n=self.action(n)
        r=self.user.get(self.public)
        self.assertEqual(r.headers['cache-control'],'no-store')
        self.assertEqual(r.json()['latest']['body'],'Đoạn 1\nĐoạn 2')
        self.assertNotIn('body',r.json()['items'][0])
        self.assertEqual(self.user.get(self.public+'/'+n['id']).json()['title'],n['title'])
        n=self.action(n,'archive')
        self.assertIsNone(self.user.get(self.public).json()['latest'])
        self.assertEqual(self.user.get(self.public).json()['total'],1)
        self.assertEqual(self.user.get(self.public+'/'+n['id']).status_code,200)

    def test_account_preference_idempotency_cross_session_and_new_notice(self):
        n=self.action(self.draft())
        endpoint=self.public+'/'+n['id']+'/dismiss'
        self.assertEqual(self.user.post(endpoint,json={'publication':n['publication']}).status_code,403)
        self.assertIsNotNone(self.user.get(self.public).json()['latest'])
        for _ in range(2):
            self.assertEqual(self.user.post(endpoint,json={'publication':n['publication']},headers={'X-QD766-CSRF':'user-csrf'}).status_code,200)
        self.assertIsNone(self.user.get(self.public).json()['latest'])
        self.assertIsNotNone(self.admin.get(self.public).json()['latest'],'Another account is independent')
        another=TestClient(self.f.app,base_url='https://testserver');another.cookies.set('qd766_session','notice-user')
        self.assertIsNone(another.get(self.public).json()['latest']);another.close()
        with self.f.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(SystemNoticeDismissal)),1)
        newer=self.action(self.draft(title='Thông báo mới'))
        self.assertEqual(self.user.get(self.public).json()['latest']['id'],newer['id'])
        self.assertEqual(self.user.get(self.public).json()['total'],2)

    def test_conflicts_csrf_validation_and_no_credit_or_jobs(self):
        n=self.draft()
        payload={k:n[k] for k in ['id','title','summary','body','kind']};payload['expectedRevision']=0
        self.assertEqual(self.admin.post(self.base,json=payload,headers=self.f.headers).status_code,409)
        self.assertEqual(self.admin.post(self.base,json=payload).status_code,403)
        for title in ['', ' '*5, 'x'*201]:
            self.assertEqual(self.admin.post(self.base,json={**payload,'id':str(uuid.uuid4()),'title':title},headers=self.f.headers).status_code,422)
        n=self.action(n)
        self.assertEqual(self.admin.post(self.base+'/'+n['id']+'/action',json={'action':'publish','expectedRevision':n['revision']},headers=self.f.headers).status_code,409)
        payload['expectedRevision']=n['revision']
        self.assertEqual(self.admin.post(self.base,json=payload,headers=self.f.headers).status_code,409)
        with self.f.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditLedgerEntry)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(AdminAudit).where(AdminAudit.action.like('system-notice.%'))),2)

    def test_publication_permissions_and_pagination(self):
        for i in range(12):self.action(self.draft(title=f'Thông báo {i}'))
        first=self.user.get(self.public).json();second=self.user.get(self.public+'?page=2').json()
        self.assertEqual((first['total'],len(first['items']),len(second['items'])),(12,10,2))
        self.assertEqual(self.admin.get(self.base+'?state=draft').json()['total'],0)
        self.assertEqual(self.user.get(self.base).status_code,403)
        self.assertEqual(self.user.post(self.base,json={},headers={'X-QD766-CSRF':'user-csrf'}).status_code,403)
        self.assertEqual(self.user.get(self.public+'?page=0').status_code,422)
        anonymous=TestClient(self.f.app,base_url='https://testserver')
        self.assertEqual(anonymous.get(self.public).status_code,401);anonymous.close()

    def test_archive_is_immutable(self):
        n=self.action(self.action(self.draft()),'archive')
        payload={k:n[k] for k in ['id','title','summary','body','kind']};payload['expectedRevision']=n['revision']
        self.assertEqual(self.admin.post(self.base,json=payload,headers=self.f.headers).status_code,409)
        self.assertEqual(self.admin.post(self.base+'/'+n['id']+'/action',json={'action':'publish','expectedRevision':n['revision']},headers=self.f.headers).status_code,409)

    def test_new_schema_on_isolated_database(self):
        import importlib.util
        from pathlib import Path
        from sqlalchemy import create_engine, inspect
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from qd766.backend.models import Base
        engine=create_engine('sqlite://')
        Base.metadata.create_all(engine,tables=[t for t in Base.metadata.sorted_tables if t.name not in {'system_notices','system_notice_dismissals'}])
        source=Path(__file__).resolve().parents[1]/'alembic/versions/20261016_0029_system_notices.py'
        spec=importlib.util.spec_from_file_location('notice_migration_test',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
                self.assertTrue(inspect(connection).has_table('system_notices'))
                self.assertTrue(inspect(connection).has_table('system_notice_dismissals'))
                self.assertEqual({c['name'] for c in inspect(connection).get_columns('system_notices')},set(SystemNotice.__table__.columns.keys()))
                module.downgrade()
                self.assertFalse(inspect(connection).has_table('system_notices'))
        engine.dispose()


if __name__=='__main__':unittest.main()
