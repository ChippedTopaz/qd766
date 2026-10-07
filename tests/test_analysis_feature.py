import unittest,importlib.util
from pathlib import Path
from dataclasses import replace
from unittest.mock import Mock
from sqlalchemy import select,func,inspect
import test_gemini_analysis as fixture
from qd766.backend.analysis_configuration import router
from qd766.backend.analysis_feature import UNAVAILABLE,verify_schema
from qd766.backend.analysis_queue import run_one
from qd766.backend.models import AnalysisFeatureControl,UserAccount,GeminiAnalysis,AnalysisConfigRevision,CreditWalletEvent
from qd766.backend.credit_wallet import balance
from alembic.operations import Operations
from alembic.migration import MigrationContext

class AnalysisFeatureTest(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PaidAnalysisTest();self.f.setUp();self.f.app.include_router(router)
        with self.f.factory.begin() as db:
            actor=db.get(UserAccount,self.f.ids[0]);actor.role='admin';actor.trial_admitted=True
        self.path='/api/v1/admin/analysis-configuration/feature'
    def tearDown(self):self.f.tearDown()
    def toggle(self,enabled,revision=0):
        return self.f.client.post(self.path,json={'enabled':enabled,'expectedRevision':revision},headers={'X-QD766-CSRF':'csrf-0'})
    def test_disabled_blocks_before_wallet_and_provider_and_persists(self):
        response=self.toggle(False);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['revision'],1)
        availability=self.f.client.get('/api/v1/me/analysis/availability')
        self.assertEqual(availability.status_code,200,availability.text)
        self.assertEqual(availability.json(),{'available':False,'message':UNAVAILABLE})
        result=self.f.post();self.assertEqual(result.status_code,503,result.text);self.assertEqual(result.json()['detail'],UNAVAILABLE)
        self.f.generate.assert_not_called()
        with self.f.factory() as db:
            self.assertEqual(db.get(AnalysisFeatureControl,1).enabled,False)
            self.assertEqual(db.scalar(select(func.count()).select_from(GeminiAnalysis)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(AnalysisConfigRevision)),0)
            self.assertEqual(balance(db,self.f.ids[0],now=self.f.now)['reserved'],0)
        self.assertEqual(self.toggle(True,1).status_code,200)
        self.assertTrue(self.f.client.get('/api/v1/me/analysis/availability').json()['available'])
        self.assertEqual(self.f.post().status_code,200)
    def test_queue_refunded_without_gemini_and_replay_safe(self):
        self.f.app.state.settings=replace(self.f.app.state.settings,gemini_queue_enabled=True)
        queued=self.f.post();self.assertEqual(queued.status_code,202,queued.text)
        self.assertEqual(self.toggle(False).status_code,200)
        provider=Mock(side_effect=AssertionError('Must not call Gemini'))
        self.assertEqual(run_one(self.f.factory,self.f.app.state.settings,generate=provider),'refunded')
        self.assertIsNone(run_one(self.f.factory,self.f.app.state.settings,generate=provider));provider.assert_not_called()
        with self.f.factory() as db:self.assertEqual(balance(db,self.f.ids[0],now=self.f.now)['reserved'],0)
        self.assertEqual(self.f.post().status_code,200,'Same-token replay must not reserve again')
        self.assertEqual(self.f.client.get('/api/v1/me/analysis/latest',params={'root_department_id':str(self.f.root),'unit_id':str(self.f.root),'period_type':'year','year':2026}).status_code,200)
    def test_running_finishes_after_switch_off(self):
        self.f.app.state.settings=replace(self.f.app.state.settings,gemini_queue_enabled=True)
        self.assertEqual(self.f.post().status_code,202)
        def generate(settings,evidence):
            self.assertEqual(self.toggle(False).status_code,200)
            return evidence['findings']
        self.assertEqual(run_one(self.f.factory,self.f.app.state.settings,generate=generate),'ready')
        self.assertFalse(self.f.client.get('/api/v1/me/analysis/availability').json()['available'])
    def test_auth_csrf_conflict_and_strict_boolean(self):
        self.assertEqual(self.f.client.post(self.path,json={'enabled':False,'expectedRevision':0}).status_code,403)
        self.assertEqual(self.f.client.post(self.path,json={'enabled':'false','expectedRevision':0},headers={'X-QD766-CSRF':'csrf-0'}).status_code,422)
        self.toggle(False);self.assertEqual(self.toggle(True,0).status_code,409)
        self.f.client.cookies.set('qd766_session','session-1')
        self.assertEqual(self.f.client.post(self.path,json={'enabled':True,'expectedRevision':1},headers={'X-QD766-CSRF':'csrf-1'}).status_code,403)
        self.f.client.cookies.clear();self.assertEqual(self.f.client.get('/api/v1/me/analysis/availability').status_code,401)
    def test_missing_schema_fail_closed(self):
        verify_schema(self.f.engine)
        AnalysisFeatureControl.__table__.drop(self.f.engine)
        with self.assertRaises(ValueError):verify_schema(self.f.engine)
        self.assertFalse(self.f.client.get('/api/v1/me/analysis/availability').json()['available'])
        self.assertEqual(self.f.post().status_code,503)
        self.assertEqual(self.toggle(False).status_code,503)
    def test_additive_migration_and_prompt_independence(self):
        AnalysisFeatureControl.__table__.drop(self.f.engine)
        path=Path(__file__).resolve().parents[1]/'alembic/versions/20261007_0022_analysis_feature_control.py'
        spec=importlib.util.spec_from_file_location('feature_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with self.f.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):module.upgrade()
        self.assertEqual(set(AnalysisFeatureControl.__table__.columns.keys()),{c['name'] for c in inspect(self.f.engine).get_columns('analysis_feature_control')})
        self.toggle(False)
        saved=self.f.client.post('/api/v1/admin/analysis-configuration',json={'expectedVersion':0,'groupId':'transparency','guidance':'Hướng dẫn phân tích nghiệp vụ đã được quản trị viên duyệt.','knowledge':'','note':'Sửa prompt khi tắt'},headers={'X-QD766-CSRF':'csrf-0'})
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertFalse(self.f.client.get('/api/v1/admin/analysis-configuration').json()['feature']['enabled'])
