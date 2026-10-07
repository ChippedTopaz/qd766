import unittest,uuid
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from qd766.backend.config import Settings
from qd766.backend.database import create_database_engine,create_session_factory
from qd766.backend.models import Base,Department,UserAccount,LoginSession,CreditWalletEnrollment,SubscriptionCycle,CreditWalletEvent,GeminiAnalysis,Snapshot,Dataset,Entity
from qd766.backend.auth import digest
from qd766.backend.credit_wallet import grant,reserve,balance
from qd766.backend.analysis import router,source_evidence,AnalysisSelection,recover_interrupted
from qd766.backend.analysis_rules import findings,metric_action
from qd766.backend.gemini_client import validate_recommendations
from qd766.backend.access_policy import enforce_public_read_only
from qd766.backend.database import get_session

class AnalysisRulesTest(unittest.TestCase):
    def test_component_guidance_is_not_repeated_group_boilerplate(self):
        group='dossier-digitized'
        result=metric_action(group,'Tỷ lệ hồ sơ có cấp kết quả giải quyết điện tử')
        self.assertIn('hồ sơ đã hoàn thành',result)
        reuse=metric_action(group,'Tỷ lệ hồ sơ khai thác, sử dụng lại thông tin, dữ liệu số hóa')
        self.assertIn('không yêu cầu',reuse);self.assertNotEqual(result,reuse)
        connection=metric_action(group,'Tỷ lệ hồ sơ số hóa có kết nối, chia sẻ dữ liệu phục vụ tái sử dụng')
        self.assertIn('ánh xạ',connection);self.assertNotEqual(connection,reuse)
        population=metric_action(group,'Tỷ lệ TTHC triển khai kết nối, chia sẻ dữ liệu dân cư phục vụ GQ TTHC')
        self.assertIn('số thủ tục',population)
        timely=metric_action('handling-satisfaction','Tỷ lệ PAKN xử lý đúng hạn')
        satisfaction=metric_action('handling-satisfaction','Tỷ lệ hài lòng trong xử lý PAKN')
        self.assertIn('thời hạn',timely);self.assertIn('không đồng nghĩa',satisfaction)
        self.assertNotEqual(timely,satisfaction)
    def test_detailed_prompt_keeps_numeric_and_schema_safety(self):
        import httpx,json
        from qd766.backend.gemini_client import generate,ANALYSIS_INSTRUCTIONS
        cards=findings([self.group(totalReceived=100,totalOnTime=80,totalOverdue=20)])
        evidence={'findings':cards,'groups':[self.group(totalReceived=100,totalOnTime=80,totalOverdue=20)],
            'reportingPeriod':{'endedAtCapture':False},'analysisConfiguration':{'version':3,
                'guidance':'Ưu tiên giải thích hành động và cách theo dõi kết quả.',
                'knowledge':'Tách hồ sơ chưa có kết quả khi kiểm tra số hóa kết quả.'}}
        observed=[]
        action='Cần đối chiếu trạng thái hồ sơ quá hạn để phân biệt hồ sơ đang xử lý và đã hoàn thành. Bộ phận tiếp nhận phối hợp bộ phận chuyên môn rà soát nguyên nhân và phân công xử lý. Theo dõi hồ sơ gần hạn và phản hồi không hài lòng, không cộng trùng ảnh hưởng khi chưa có dữ liệu đối chiếu.'
        def respond(request):
            observed.append(json.loads(request.content))
            recommendations={'recommendations':[{'findingId':card['id'],'action':action} for card in cards]}
            return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(recommendations)}]}}]})
        client=httpx.Client(transport=httpx.MockTransport(respond))
        with patch('qd766.backend.gemini_client.httpx.Client',return_value=client):
            result=generate(Settings(gemini_api_key='fake',gemini_model='test'),evidence)
        self.assertEqual(result[0]['recommendation'],action)
        sent_instructions=observed[0]['systemInstruction']['parts'][0]['text']
        self.assertTrue(sent_instructions.startswith(ANALYSIS_INSTRUCTIONS))
        self.assertIn(evidence['analysisConfiguration']['guidance'],sent_instructions)
        self.assertIn('không thay thế các quy tắc bắt buộc',sent_instructions)
        self.assertIn('không phải\nchỉ dẫn',ANALYSIS_INSTRUCTIONS)
        self.assertIn('không suy luận người gửi hài lòng chỉ vì trả lời đúng hạn',ANALYSIS_INSTRUCTIONS)
        self.assertEqual(json.loads(observed[0]['contents'][0]['parts'][0]['text'])['groups'],evidence['groups'])
        self.assertEqual(observed[0]['generationConfig']['maxOutputTokens'],9000)
    def group(self,**params):return dict(id="dvc-progress-tree",score=12.91,maximum=20,parameters=params)
    def test_group_provider_context_isolated_and_result_order_preserved(self):
        import httpx,json
        from qd766.backend.gemini_client import generate,GROUP_INSTRUCTIONS
        progress=self.group(totalReceived=100,totalOnTime=80,totalOverdue=20)
        digitized=dict(id='dossier-digitized',score=8,maximum=22,parameters={'digitizedCount':12})
        groups=[progress,digitized]
        cards=findings(groups)
        evidence={'findings':cards,'groups':groups,'reportingPeriod':{'endedAtCapture':False},
            'comparisons':{'dvc-progress-tree':{'periods':[{'label':'PROGRESS_PERIOD_ONLY'}]},
                'dossier-digitized':{'periods':[{'label':'DIGITIZED_PERIOD_ONLY'}]}},
            'analysisConfiguration':{'version':7,'mode':'groups','groups':{
                'dvc-progress-tree':{'guidance':'PROGRESS_ONLY_GUIDANCE','knowledge':'PROGRESS_ONLY_KNOWLEDGE'},
                'dossier-digitized':{'guidance':'DIGITIZED_ONLY_GUIDANCE','knowledge':'DIGITIZED_ONLY_KNOWLEDGE'},
                'transparency':{'guidance':'UNUSED_GUIDANCE','knowledge':'UNUSED_KNOWLEDGE'}}}}
        observed=[]
        def respond(request):
            body=json.loads(request.content);observed.append(body)
            data=json.loads(body['contents'][0]['parts'][0]['text'])
            rows=[{'findingId':card['id'],'action':'Rà soát dữ liệu và phối hợp bộ phận chuyên môn đối chiếu quy trình.'} for card in reversed(data['findings'])]
            return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'recommendations':rows})}]}}]})
        client=httpx.Client(transport=httpx.MockTransport(respond))
        with patch('qd766.backend.gemini_client.httpx.Client',return_value=client):
            result=generate(Settings(gemini_api_key='fake',gemini_model='test'),evidence)
        self.assertEqual(len(observed),2)
        self.assertEqual([card['id'] for card in result],[card['id'] for card in cards])
        for body in observed:
            raw=json.dumps(body);data=json.loads(body['contents'][0]['parts'][0]['text'])
            key=data['analysisConfiguration']['groupId']
            self.assertEqual(len(data['groups']),1)
            self.assertTrue(all(card['groupId']==key for card in data['findings']))
            self.assertEqual(data['groups'][0]['id'],key)
            self.assertEqual(data['comparisons'],evidence['comparisons'][key])
            self.assertNotIn('UNUSED_',raw)
            forbidden='DIGITIZED_ONLY' if key=='dvc-progress-tree' else 'PROGRESS_ONLY'
            self.assertNotIn(forbidden,raw)
            self.assertTrue(body['systemInstruction']['parts'][0]['text'].startswith(GROUP_INSTRUCTIONS))
        self.assertEqual(evidence['analysisConfiguration']['groups']['transparency']['knowledge'],'UNUSED_KNOWLEDGE')

    def test_group_budget_expires_without_provider_call(self):
        from qd766.backend.gemini_client import generate
        cards=findings([self.group(totalReceived=10,totalOnTime=9,totalOverdue=1)])
        evidence={'findings':cards,'groups':[],'analysisConfiguration':{'version':1,'mode':'groups',
            'groups':{'dvc-progress-tree':{'guidance':'Test guidance','knowledge':''}}}}
        with patch('qd766.backend.gemini_client.time.monotonic',side_effect=[0,181]),patch('qd766.backend.gemini_client.httpx.Client') as client:
            with self.assertRaises(TimeoutError):generate(Settings(gemini_api_key='fake',gemini_model='test'),evidence)
        client.return_value.__enter__.return_value.post.assert_not_called()
    def test_conservation_and_overdue(self):
        rows=findings([self.group(totalReceived=33699,totalOnTime=21751,totalOverdue=11948)])
        self.assertEqual(rows[0]["id"],"overdue");self.assertIn("11948/33699",rows[0]["evidence"])
        with self.assertRaises(ValueError):findings([self.group(totalReceived=100,totalOnTime=80,totalOverdue=10)])
        rows=findings([self.group(totalReceived=0,totalOnTime=0,totalOverdue=0)])
        self.assertFalse(any(r["id"]=="overdue" for r in rows))
    def test_day_decline_requires_three_real_dates_and_same_maximum(self):
        days=[dict(reportDate=f"2026-10-0{i+6}",groups={"dvc-progress-tree":dict(score=18-i,maximum=20)}) for i in range(3)]
        self.assertTrue(any(r["id"].endswith(":decline") for r in findings([],days)))
        days[-1]["reportDate"]="2026-10-10"
        self.assertEqual(findings([],days),[])
        days[-1]["reportDate"]="2026-10-08";days[-1]["groups"]["dvc-progress-tree"]["maximum"]=18
        self.assertEqual(findings([],days),[])
    def test_ai_cannot_add_findings_or_numbers(self):
        cards=findings([self.group(totalReceived=10,totalOnTime=9,totalOverdue=1)])
        good={"recommendations":[dict(findingId=c["id"],action="Rà soát hồ sơ quá hạn và phân công xử lý.") for c in cards]}
        self.assertEqual(len(validate_recommendations(good,cards)),len(cards))
        good["recommendations"][0]["action"]="Sẽ tăng thêm 5 điểm."
        with self.assertRaises(ValueError):validate_recommendations(good,cards)
        with self.assertRaises(ValueError):validate_recommendations({"recommendations":[]},cards)

class PaidAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc);self.root=uuid.uuid4();self.ids=[uuid.uuid4(),uuid.uuid4()]
        self.engine=create_database_engine(Settings(database_url="sqlite+pysqlite://"));Base.metadata.create_all(self.engine)
        self.factory=create_session_factory(self.engine);self.factory.configure(info={"source_wallet_enabled":True})
        self.app=FastAPI();self.app.state.session_factory=self.factory
        self.app.state.settings=Settings(public_read_only=True,require_login=True,paid_requests_enabled=True,
            gemini_analysis_enabled=True,gemini_api_key="fake-key-never-sent",gemini_model="test-model")
        self.app.middleware("http")(enforce_public_read_only);self.app.include_router(router)
        with self.factory.begin() as db:
            db.add(Department(id=self.root,name="Tỉnh kiểm thử"));db.flush()
            for i,aid in enumerate(self.ids):
                db.add(UserAccount(id=aid,external_subject=str(aid),display_name="Test",root_department_id=self.root))
                db.flush();db.add(CreditWalletEnrollment(account_id=aid,created_at=self.now))
                db.add(SubscriptionCycle(account_id=aid,operation_key="test",tier="province",origin="trial",
                    starts_at=self.now-timedelta(days=1),ends_at=self.now+timedelta(days=5),included_credit=100))
                db.add(LoginSession(token_hash=digest(f"session-{i}"),account_id=aid,csrf_token=f"csrf-{i}",expires_at=self.now+timedelta(hours=1)))
                grant(db,aid,12,source="subscription",operation_key="sub",now=self.now,expires_at=self.now+timedelta(days=1))
                grant(db,aid,100,source="purchased",operation_key="buy",now=self.now)
        self.client=TestClient(self.app);self.client.cookies.set("qd766_session","session-0")
        self.body=dict(rootDepartmentId=str(self.root),unitId=str(self.root),periodType="year",year=2026,periodValue=None,token=str(uuid.uuid4()),expectedCredits=20,
            groupIds=['dvc-progress-tree','dossier-digitized','handling-satisfaction','formality-online-payment-tree'])
        cards=findings([dict(id="dvc-progress-tree",score=12.91,maximum=20,parameters=dict(totalReceived=100,totalOnTime=65,totalOverdue=35))])
        self.evidence=dict(capturedAt=self.now.isoformat(),findings=cards,limitations=[])
        self.source=patch("qd766.backend.analysis.source_evidence",return_value=self.evidence);self.source.start()
        self.provider=patch("qd766.backend.analysis.gemini_client.generate",return_value=cards);self.generate=self.provider.start()
    def tearDown(self):self.source.stop();self.provider.stop();self.engine.dispose()
    def post(self,**changes):return self.client.post("/api/v1/me/analysis",json={**self.body,**changes},headers={"X-QD766-CSRF":"csrf-0"})
    def query(self):return dict(root_department_id=str(self.root),unit_id=str(self.root),period_type="year",year=2026)
    def test_success_replay_and_read_free(self):
        result=self.post();self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()["state"],"ready")
        self.assertEqual(result.json()["availableCredits"],92)
        self.assertEqual(self.post().json()["id"],result.json()["id"]);self.generate.assert_called_once()
        with self.factory() as db:
            events=db.scalars(select(CreditWalletEvent).where(CreditWalletEvent.kind=="reserve")).all()
            self.assertEqual([(a["source"],a["amount"]) for a in events[0].details["allocations"]],[("subscription",12),("purchased",8)])
            self.assertEqual(db.scalar(select(func.count()).select_from(CreditWalletEvent).where(CreditWalletEvent.kind=="charge")),1)
        saved=self.client.get("/api/v1/me/analysis/latest",params=self.query())
        self.assertEqual(saved.status_code,200,saved.text);self.assertEqual(saved.json()["analysis"]["id"],result.json()["id"])
        self.generate.assert_called_once()
    def test_selected_groups_cost_once_and_price_tampering_rejected(self):
        from qd766.backend.analysis_rules import LABELS
        self.assertEqual(self.post(groupIds=['dvc-progress-tree'],expectedCredits=20).status_code,422)
        self.assertEqual(self.post(groupIds=['dvc-progress-tree','dvc-progress-tree'],expectedCredits=10).status_code,422)
        self.assertEqual(self.post(groupIds=[],expectedCredits=0).status_code,422)
        self.assertEqual(self.post(groupIds=['fake'],expectedCredits=5).status_code,422)
        one=self.post(groupIds=['dvc-progress-tree'],expectedCredits=5)
        self.assertEqual(one.status_code,200,one.text);self.assertEqual(one.json()['credits'],5)
        self.assertEqual(one.json()['availableCredits'],107)
        self.assertEqual(self.post(groupIds=['dvc-progress-tree'],expectedCredits=5).json()['id'],one.json()['id'])
        all_groups=list(LABELS)
        six=self.post(groupIds=all_groups,expectedCredits=30,token=str(uuid.uuid4()))
        self.assertEqual(six.json()['credits'],30);self.assertEqual(six.json()['availableCredits'],77)
        self.assertEqual(self.post(groupIds=all_groups,expectedCredits=5,token=str(uuid.uuid4())).status_code,422)
        self.assertEqual(self.post(groupIds=['transparency'],expectedCredits=5).status_code,409)
        with self.factory() as db:
            events=list(db.scalars(select(CreditWalletEvent).where(CreditWalletEvent.kind=='charge')))
            self.assertEqual(sorted(event.amount for event in events),[5,30])
    def test_five_credit_failure_refunds_and_legacy_result_stays_twenty(self):
        self.generate.side_effect=TimeoutError('failure')
        result=self.post(groupIds=['dvc-progress-tree'],expectedCredits=5)
        self.assertEqual(result.json()['state'],'failed');self.assertEqual(result.json()['availableCredits'],112)
        self.assertEqual(result.json()['heldCredits'],0)
        from qd766.backend.analysis import serialize
        with self.factory() as db:
            old=GeminiAnalysis(id=uuid.uuid4(),account_id=self.ids[0],request_token=uuid.uuid4(),context={},
                evidence={'capturedAt':self.now.isoformat()},result={'cards':[]},model='legacy',created_at=self.now,state='ready')
            self.assertEqual(serialize(old,db)['credits'],20)
    def test_provider_failure_refunds_and_replay_does_not_call_again(self):
        self.generate.side_effect=TimeoutError("private provider error")
        result=self.post();self.assertEqual(result.json()["state"],"failed");self.assertEqual(result.json()["availableCredits"],112)
        self.assertNotIn("private",result.text);self.assertEqual(self.post().json()["state"],"failed");self.generate.assert_called_once()
        with self.factory() as db:self.assertEqual(balance(db,self.ids[0],now=self.now)["reserved"],0)
    def test_multiple_groups_one_charge_or_full_refund(self):
        import httpx,json
        self.provider.stop()
        groups=[dict(id='dvc-progress-tree',score=12,maximum=20,parameters=dict(totalReceived=10,totalOnTime=9,totalOverdue=1)),
                dict(id='dossier-digitized',score=8,maximum=22,parameters={})]
        self.evidence.update(groups=groups,findings=findings(groups),analysisConfiguration={'mode':'groups','version':1,
            'groups':{group['id']:{'guidance':'Phân tích nghiệp vụ riêng của nhóm.','knowledge':''} for group in groups}})
        for succeeds in (True,False):
            with self.subTest(succeeds=succeeds):
                requests=[]
                def respond(request):
                    data=json.loads(json.loads(request.content)['contents'][0]['parts'][0]['text']);requests.append(data)
                    if not succeeds and len(requests)==2:return httpx.Response(400)
                    rows=[dict(findingId=card['id'],action='Đối chiếu nghiệp vụ và phối hợp xử lý nguyên nhân.') for card in data['findings']]
                    return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'recommendations':rows})}]}}]})
                client=httpx.Client(transport=httpx.MockTransport(respond))
                with patch('qd766.backend.gemini_client.httpx.Client',return_value=client):result=self.post(token=str(uuid.uuid4()))
                self.assertEqual(result.json()['state'],'ready' if succeeds else 'failed')
                self.assertEqual(len(requests),2)
                with self.factory() as db:
                    job=result.json()['id']
                    events=list(db.scalars(select(CreditWalletEvent).where(CreditWalletEvent.event_key.in_([kind+':analysis:'+job for kind in ('reserve','charge','refund')]))))
                    self.assertEqual(sum(event.kind=='reserve' for event in events),1)
                    self.assertEqual(sum(event.kind=='charge' for event in events),int(succeeds))
                    self.assertEqual(sum(event.kind=='refund' for event in events),int(not succeeds))
                    self.assertEqual(balance(db,self.ids[0],now=self.now)['reserved'],0)
    def test_http_503_retries_share_one_hold_and_charge_or_refund(self):
        import httpx,json
        self.provider.stop()
        for succeeds in (True,False):
            with self.subTest(succeeds=succeeds):
                calls=[]
                def respond(request):
                    calls.append(request)
                    if len(calls)<3 or not succeeds:return httpx.Response(503,json={"error":"private-body"})
                    recommendations=[dict(findingId=c["id"],action="Rà soát hồ sơ và phân công xử lý.") for c in self.evidence["findings"]]
                    return httpx.Response(200,json={"candidates":[{"finishReason":"STOP","content":{"parts":[
                        {"text":json.dumps({"recommendations":recommendations})}]}}]})
                client=httpx.Client(transport=httpx.MockTransport(respond))
                with patch("qd766.backend.gemini_client.httpx.Client",return_value=client),patch("qd766.backend.gemini_client.time.sleep"):
                    result=self.post(token=str(uuid.uuid4()))
                self.assertEqual(result.json()["state"],"ready" if succeeds else "failed")
                self.assertEqual(len(calls),3)
                with self.factory() as db:
                    row=db.get(GeminiAnalysis,uuid.UUID(result.json()["id"]))
                    events=list(db.scalars(select(CreditWalletEvent).where(
                        CreditWalletEvent.event_key.in_([kind+":analysis:"+str(row.id) for kind in ("reserve","charge","refund")]))))
                    self.assertEqual(sum(e.kind=="reserve" for e in events),1)
                    self.assertEqual(sum(e.kind=="charge" for e in events),int(succeeds))
                    self.assertEqual(sum(e.kind=="refund" for e in events),int(not succeeds))
                    self.assertEqual(balance(db,self.ids[0],now=self.now)["available"],92)
                    self.assertEqual(balance(db,self.ids[0],now=self.now)["reserved"],0)
    def test_provider_has_no_open_transaction(self):
        observed=[]
        def dependency():
            with self.factory() as db:
                observed.append(db)
                yield db
        self.app.dependency_overrides[get_session]=dependency
        cards=self.evidence["findings"]
        def generate(*args):
            self.assertFalse(observed[-1].in_transaction())
            return cards
        self.generate.side_effect=generate
        self.assertEqual(self.post().json()["state"],"ready")
    def test_additive_migration_matches_model(self):
        import importlib.util
        from pathlib import Path
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from sqlalchemy import inspect
        # Own in-memory test DB only; no office database or schema involved.
        GeminiAnalysis.__table__.drop(self.engine)
        path=Path(__file__).resolve().parents[1]/"alembic/versions/20261006_0018_gemini_analysis.py"
        spec=importlib.util.spec_from_file_location("analysis_migration",path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with self.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):module.upgrade()
        self.assertEqual({c["name"] for c in inspect(self.engine).get_columns("gemini_analyses")},set(GeminiAnalysis.__table__.columns.keys()))
    def test_expired_insufficient_unconfigured_and_csrf_do_not_hold(self):
        with self.factory.begin() as db:
            cycle=db.scalar(select(SubscriptionCycle).where(SubscriptionCycle.account_id==self.ids[0]));cycle.ends_at=self.now-timedelta(seconds=1)
        self.assertEqual(self.post().status_code,403);self.generate.assert_not_called()
        with self.factory.begin() as db:
            cycle=db.scalar(select(SubscriptionCycle).where(SubscriptionCycle.account_id==self.ids[0]));cycle.ends_at=self.now+timedelta(days=1)
            reserve(db,self.ids[0],100,request_key="other",now=self.now)
        self.assertEqual(self.post().status_code,402)
        self.app.state.settings=Settings(public_read_only=True,require_login=True,paid_requests_enabled=True)
        self.assertEqual(self.post().status_code,503)
        self.assertEqual(self.client.post("/api/v1/me/analysis",json=self.body).status_code,403)
    def test_scope_cost_tamper_other_account_and_interrupt_recovery(self):
        self.assertEqual(self.post(rootDepartmentId=str(uuid.uuid4())).status_code,403)
        self.assertEqual(self.post(expectedCredits=1).status_code,422)
        result=self.post();self.client.cookies.set("qd766_session","session-1")
        self.assertIsNone(self.client.get("/api/v1/me/analysis/latest",params=self.query()).json()["analysis"])
        with self.factory.begin() as db:
            row=GeminiAnalysis(id=uuid.uuid4(),account_id=self.ids[1],request_token=uuid.uuid4(),context={},evidence=self.evidence,
                model="test",created_at=self.now-timedelta(minutes=6),state="running")
            db.add(row);reserve(db,self.ids[1],20,request_key="analysis:"+str(row.id),now=self.now)
            recover_interrupted(db,self.ids[1],self.now);recover_interrupted(db,self.ids[1],self.now)
            self.assertEqual(row.state,"failed");self.assertEqual(balance(db,self.ids[1],now=self.now)["available"],112)
    def test_source_selection_contains_only_chosen_agency(self):
        self.source.stop()
        agency=uuid.uuid4();other=uuid.uuid4()
        with self.factory.begin() as db:
            db.add_all([Department(id=agency,name="Cơ quan A"),Department(id=other,name="Cơ quan B")]);db.flush()
            snap=Snapshot(snapshot_key="test-snapshot",schema_version=1,root_department_id=self.root,period_type="year",year=2026,
                period_value=None,scope="all",state="complete",created_at=self.now);db.add(snap);db.flush()
            dataset=Dataset(snapshot_id=snap.id,position=1,group_name="dvc-progress-tree",schema_kind="parameters",
                formula_status="verified",score_policy="api-authoritative",raw_path="private",raw_sha256="a"*64);db.add(dataset);db.flush()
            for i,unit in enumerate([agency,other]):db.add(Entity(dataset_id=dataset.id,department_id=unit,entity_kind="child",position=i,
                api_score=12.91,api_max_score=20,score_source="dvcqg-api",parameters={"totalReceived":100,"totalOnTime":65,"totalOverdue":35,"rawDebug":"private-marker"}))
        with self.factory() as db:
            evidence=source_evidence(db,AnalysisSelection(rootDepartmentId=self.root,unitId=agency,periodType="year",year=2026))
            self.assertEqual(evidence["organization"],"Cơ quan A");self.assertNotIn("Cơ quan B",str(evidence));self.assertNotIn("private",str(evidence))
            self.assertEqual(len(evidence['groups']),1)
            self.assertEqual(evidence['groups'][0]['parameters']['totalOverdue'],35)
            self.assertEqual(evidence['reportingPeriod']['end'],'2026-12-31')

if __name__=="__main__":unittest.main()
