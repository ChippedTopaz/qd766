import copy,unittest,uuid
from datetime import date,datetime,timedelta,timezone
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from qd766.backend.app import create_app
from qd766.backend.config import Settings
from qd766.backend.models import Base,DailyObservation,UserAccount,LoginSession,CollectionJob,PaidDataRequest
from qd766.backend.auth import digest
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.national_summaries import store_national_summary
from qd766.backend.dashboard import NATIONAL_GROUP_CODES
from qd766.national_summary import NationalSummaryCapture
from qd766.periods import PeriodSelection
from test_backend import snapshot_payload,ROOT_ID,CHILD_ID

class SavedDaySelectionTests(unittest.TestCase):
 def setUp(self):
  self.app=create_app(Settings(database_url='sqlite://',public_read_only=True,require_login=True,
   google_client_id='test',google_client_secret='test',google_redirect_uri='https://example.test/api/v1/auth/google/callback'))
  Base.metadata.create_all(self.app.state.engine);self.factory=self.app.state.session_factory
  self.ids={};self.user=uuid.uuid4();self.peer=uuid.uuid4()
  with self.factory.begin() as db:
   for index,day in enumerate((7,8)):
    stamp=datetime(2026,10,day+1,0,tzinfo=timezone.utc)
    payload=snapshot_payload();dataset=payload['datasets'][0]
    dataset['root']['apiScore']=index+1;dataset['children'][0]['apiScore']=index+1
    peer=copy.deepcopy(dataset['children'][0]);peer['departmentId']=str(self.peer);peer['departmentName']='Peer';peer['parameters']={'private':12345};dataset['children'].append(peer)
    payload['period']={'type':'month','year':2026,'month':10}
    payload['datasets']=[dict(copy.deepcopy(dataset),group=group,period=payload['period']) for group in NATIONAL_GROUP_CODES]
    payload['status'].update(requiredGroups=list(NATIONAL_GROUP_CODES),loadedGroups=list(NATIONAL_GROUP_CODES))
    snap=store_normalized_snapshot(db,payload,observation_id='selection-day-'+str(day));snap.created_at=stamp
    rows=[{'departmentId':ROOT_ID if n==0 else str(uuid.uuid4()),'departmentName':'Province '+str(n),
           'totalScore':61+index*10+n/100,'groupScores':{code:index+1 for code in NATIONAL_GROUP_CODES.values()}} for n in range(34)]
    summary,_=store_national_summary(db,NationalSummaryCapture(PeriodSelection('month',2026,10),{},
       {'evaluation':rows},str(index+1)*64,stamp),observation_id='selection-summary-'+str(day))
    db.add(DailyObservation(block_key='selection-day-'+str(day),report_date=date(2026,10,day),
       root_department_id=uuid.UUID(ROOT_ID),period_type='month',year=2026,period_value=10,
       snapshot_id=snap.id,national_summary_id=summary.id,captured_at=stamp))
    self.ids[day]=snap.id
   db.add(UserAccount(id=self.user,external_subject=str(self.user),display_name='Viewer',plan='free',
       trial_admitted=True,root_department_id=uuid.UUID(ROOT_ID),access_tier='province'))
   db.flush();db.add(LoginSession(token_hash=digest('day-view'),account_id=self.user,csrf_token='test',
       expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
  self.client=TestClient(self.app);self.client.cookies.set('qd766_session','day-view')
  self.query={'root_department_id':ROOT_ID,'period_type':'month','year':2026,'period_value':10,'scope':'all'}
 def tearDown(self):self.app.state.engine.dispose()
 def get(self,**changes):return self.client.get('/api/v1/dashboard/selection',params={**self.query,**changes})
 def test_exact_day_snapshot_summary_cache_and_latest_unchanged(self):
  for day,score in ((7,61),(8,71),(7,61)):
   response=self.get(report_date=f'2026-10-{day:02}');self.assertEqual(response.status_code,200,response.text)
   body=response.json();self.assertEqual(body['metadata']['reportDate'],f'2026-10-{day:02}')
   self.assertEqual(body['snapshot']['provinceAggregatedScore'],score)
   self.assertEqual(body['benchmarks'][0]['totalScore'],score)
   self.assertEqual(body['snapshot']['datasets'][0]['children'][0]['apiScore'],1 if day==7 else 2)
  self.assertEqual(self.get().json()['snapshot']['provinceAggregatedScore'],71)
  with self.factory() as db:
   self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
   self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)
 def test_missing_and_out_of_period_days_do_not_fall_back(self):
  self.assertEqual(self.get(report_date='2026-10-09').status_code,404)
  for invalid in ('2026-09-07','2025-10-07','2026-10-40','bad'):
   self.assertEqual(self.get(report_date=invalid).status_code,422)
  self.assertEqual(self.get(report_date='2026-10-07',formality_id=str(uuid.uuid4())).status_code,403)
  self.assertEqual(self.get(report_date='2026-10-07',scope='formality',formality_id=str(uuid.uuid4())).status_code,403)
 def test_group_export_uses_same_saved_day(self):
  response=self.client.get('/api/v1/dashboard/group-export',params={**self.query,'report_date':'2026-10-07','group':'transparency'})
  self.assertEqual(response.status_code,200,response.text)
  self.assertEqual(response.json()['delivery']['reportDate'],'2026-10-07')
  self.assertEqual(response.json()['groups'][0]['entities'][0]['apiScore'],1)
 def test_unauthorized_root_and_anonymous_are_blocked(self):
  self.assertEqual(self.get(report_date='2026-10-07',root_department_id=str(uuid.uuid4())).status_code,403)
  self.client.cookies.clear();self.assertEqual(self.get(report_date='2026-10-07').status_code,401)
 def test_agency_still_only_gets_own_business_details(self):
  with self.factory.begin() as db:
   account=db.get(UserAccount,self.user);account.access_tier='agency';account.unit_department_id=uuid.UUID(CHILD_ID)
  response=self.get(report_date='2026-10-07');self.assertEqual(response.status_code,200,response.text)
  payload=response.json()['snapshot']
  for group in payload['datasets']:
   self.assertEqual(group['root']['metrics'],[]);self.assertEqual(group['root']['parameters'],{})
   self.assertTrue(next(e for e in group['children'] if e['departmentId']==CHILD_ID)['metrics'])
   other=next(e for e in group['children'] if e['departmentId']==str(self.peer))
   self.assertEqual(other['metrics'],[]);self.assertEqual(other['parameters'],{})
  self.assertEqual(self.get(report_date='2026-10-07',root_department_id=str(uuid.uuid4())).status_code,403)
