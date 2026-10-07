import unittest,uuid,importlib.util
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from sqlalchemy import select,func,inspect
from alembic.operations import Operations
from alembic.migration import MigrationContext
import test_gemini_analysis as fixture
from qd766.backend.analysis_configuration import router,configuration,DEFAULT_GUIDANCE
from qd766.backend.models import UserAccount,AnalysisConfigHead,AnalysisConfigRevision,AdminAudit,GeminiAnalysis
from qd766.backend.analysis_queue import run_one

class ConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PaidAnalysisTest();self.f.setUp();self.f.app.include_router(router)
        with self.f.factory.begin() as db:
            actor=db.get(UserAccount,self.f.ids[0]);actor.role='admin';actor.trial_admitted=True
        self.path='/api/v1/admin/analysis-configuration'
        self.payload=dict(expectedVersion=0,guidance='Phân tích cụ thể từng khâu nghiệp vụ và đề xuất cách theo dõi.',knowledge='Hồ sơ đang giải quyết chưa có kết quả cần tách khi kiểm tra số hóa kết quả.',note='Bổ sung nghiệp vụ số hóa')
    def tearDown(self):self.f.tearDown()
    def save(self,**changes):
        return self.f.client.post(self.path,json={**self.payload,**changes},headers={'X-QD766-CSRF':'csrf-0'})
    def test_default_get_read_only_save_history_and_preview_restore(self):
        response=self.f.client.get(self.path);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['version'],0);self.assertTrue(response.json()['schemaReady'])
        with self.f.factory() as db:self.assertEqual(db.scalar(select(func.count()).select_from(AnalysisConfigRevision)),0)
        saved=self.save();self.assertEqual(saved.status_code,200,saved.text);self.assertEqual(saved.json()['version'],1)
        current=self.f.client.get(self.path).json();self.assertEqual(current['knowledge'],self.payload['knowledge'])
        self.assertEqual(current['history'][0]['version'],1)
        preview=self.f.client.get(self.path,params={'version':0}).json()
        self.assertEqual(preview['guidance'],DEFAULT_GUIDANCE);self.assertEqual(preview['activeVersion'],1)
        self.assertEqual(self.f.client.get(self.path).json()['version'],1)
        self.assertEqual(self.save(expectedVersion=1,guidance=preview['guidance'],knowledge='',note='Khôi phục mặc định').json()['version'],2)
        self.assertEqual(self.f.client.get(self.path,params={'version':1}).json()['knowledge'],self.payload['knowledge'])
        with self.f.factory() as db:self.assertEqual(db.scalar(select(func.count()).select_from(AdminAudit)),2)
    def test_stale_version_and_extra_settings_rejected(self):
        self.save();self.assertEqual(self.save().status_code,409)
        self.assertEqual(self.save(expectedVersion=1,credits=0).status_code,422)
        self.assertEqual(self.save(expectedVersion=1,guidance=' '*30).status_code,422)
        self.assertEqual(self.save(expectedVersion=1,knowledge='x'*30001).status_code,422)
        self.assertEqual(self.save(expectedVersion=1,knowledge='bad\x00data').status_code,422)
    def test_csrf_nonadmin_and_logged_out(self):
        self.assertEqual(self.f.client.post(self.path,json=self.payload).status_code,403)
        self.f.client.cookies.set('qd766_session','session-1')
        self.assertEqual(self.f.client.get(self.path).status_code,403)
        self.assertEqual(self.f.client.post(self.path,json=self.payload,headers={'X-QD766-CSRF':'csrf-1'}).status_code,403)
        self.f.client.cookies.clear();self.assertEqual(self.f.client.get(self.path).status_code,401)
    def test_missing_schema_falls_back_readonly_but_save_blocked(self):
        AnalysisConfigHead.__table__.drop(self.f.engine);AnalysisConfigRevision.__table__.drop(self.f.engine)
        current=self.f.client.get(self.path).json();self.assertFalse(current['schemaReady']);self.assertEqual(current['version'],0)
        self.assertEqual(self.save().status_code,503)
        with self.f.factory() as db:self.assertEqual(configuration(db)['guidance'],DEFAULT_GUIDANCE)
    def test_configuration_pinned_to_queue_evidence_not_execution_time(self):
        self.save();self.f.app.state.settings=replace(self.f.app.state.settings,gemini_queue_enabled=True)
        self.f.source.stop()
        with patch('qd766.backend.analysis.source_evidence',side_effect=lambda db,_:{**self.f.evidence,'analysisConfiguration':configuration(db)}):
            result=self.f.post();self.assertEqual(result.status_code,202,result.text)
        self.save(expectedVersion=1,knowledge='Kiến thức mới sau khi người dùng đã xác nhận.')
        observed=[]
        def generate(settings,evidence):observed.append(evidence);return self.f.evidence['findings']
        self.assertEqual(run_one(self.f.factory,self.f.app.state.settings,generate=generate),'ready')
        self.assertEqual(observed[0]['analysisConfiguration']['version'],1)
        self.assertEqual(observed[0]['analysisConfiguration']['knowledge'],self.payload['knowledge'])
        with self.f.factory() as db:
            row=db.get(GeminiAnalysis,uuid.UUID(result.json()['id']));self.assertEqual(row.result['configurationVersion'],1)
    def test_additive_migration(self):
        AnalysisConfigHead.__table__.drop(self.f.engine);AnalysisConfigRevision.__table__.drop(self.f.engine)
        path=Path(__file__).resolve().parents[1]/'alembic/versions/20261007_0020_analysis_configuration.py'
        spec=importlib.util.spec_from_file_location('config_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with self.f.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):module.upgrade()
        for model in (AnalysisConfigHead,AnalysisConfigRevision):
            self.assertEqual(set(model.__table__.columns.keys()),{c['name'] for c in inspect(self.f.engine).get_columns(model.__tablename__)})

if __name__=='__main__':unittest.main()
