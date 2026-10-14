import unittest,uuid,time,copy
from datetime import date,datetime,timezone
from sqlalchemy import select,func,event
from qd766.backend.models import DailyObservation,Snapshot,Dataset,Entity,UserAccount,CollectionJob,PaidDataRequest
import test_daily_selection as daily_fixture
from test_backend import ROOT_ID,CHILD_ID,snapshot_payload


class DailyIndicatorComparisonTests(unittest.TestCase):
 def setUp(self):
  self.fixture=daily_fixture.SavedDaySelectionTests();self.fixture.setUp()
  self.client=self.fixture.client;self.factory=self.fixture.factory;self.app=self.fixture.app
  self.query={**self.fixture.query,'unit_id':CHILD_ID,'group':'formality-online-payment-tree'}
  with self.factory.begin() as db:
   for day,values in ((7,(1000,1300)),(8,(1200,1400))):
    row=db.scalar(select(Entity).join(Dataset).where(Dataset.snapshot_id==self.fixture.ids[day],
     Dataset.group_name=='formality-online-payment-tree',Entity.department_id==uuid.UUID(CHILD_ID)))
    row.parameters={'totalDossierOnlinePaymentSuccess':values[0],'totalDossierFinancialObligation':values[1],
     'totalFeeDossierFormality':32,'totalFeeFormality':40,'totalDossierOnlineFormalityPaymentSuccess':30,
     'totalFeeDossierFormalityDistinct':40,'sensitiveNote':'not a numeric business parameter','scoreDelta':12345}
 def tearDown(self):self.fixture.tearDown()
 def get(self,**changes):return self.client.get('/api/v1/dashboard/daily-indicator-comparison',params={**self.query,**changes})
 def agency(self):
  with self.factory.begin() as db:
   account=db.get(UserAccount,self.fixture.user);account.access_tier='agency';account.unit_department_id=uuid.UUID(CHILD_ID)
 def add_day(self,db,day,amount,version='one'):
  from qd766.backend.importer import store_normalized_snapshot
  from qd766.backend.dashboard import NATIONAL_GROUP_CODES
  payload=snapshot_payload();dataset=payload['datasets'][0]
  dataset['children'][0]['parameters']={'totalDossierOnlinePaymentSuccess':amount,'totalDossierFinancialObligation':2000,'privateNote':'must not leak'}
  payload['period']={'type':'month','year':2026,'month':10}
  payload['datasets']=[dict(copy.deepcopy(dataset),group=group,period=payload['period']) for group in NATIONAL_GROUP_CODES]
  payload['status'].update(requiredGroups=list(NATIONAL_GROUP_CODES),loadedGroups=list(NATIONAL_GROUP_CODES))
  snap=store_normalized_snapshot(db,payload,observation_id=f'chart-{day}-{version}')
  stamp=datetime(2026,10,day+1,1 if version=='two' else 0,tzinfo=timezone.utc);snap.created_at=stamp
  summary=db.scalar(select(DailyObservation.national_summary_id).where(DailyObservation.report_date==date(2026,10,8)))
  db.add(DailyObservation(block_key=f'chart-{day}-{version}',report_date=date(2026,10,day),
   root_department_id=uuid.UUID(ROOT_ID),period_type='month',year=2026,period_value=10,
   snapshot_id=snap.id,national_summary_id=summary,captured_at=stamp))
 def test_seven_calendar_days_batched_exact_values_and_account_scope(self):
  with self.factory.begin() as db:
   for day in (6,9,10,11,12):self.add_day(db,day,day*100)
   self.add_day(db,9,999,'two')
  self.agency();sql=[];engine=self.app.state.engine;counter=lambda *args:sql.append(args[2])
  event.listen(engine,'before_cursor_execute',counter)
  try:response=self.get(current_date='2026-10-12',baseline_date='2026-10-06')
  finally:event.remove(engine,'before_cursor_execute',counter)
  self.assertEqual(response.status_code,200,response.text);body=response.json()
  self.assertEqual([r['reportDate'] for r in body['series']],[f'2026-10-{d:02}' for d in range(6,13)])
  self.assertEqual([r['entity']['parameters']['totalDossierOnlinePaymentSuccess'] for r in body['series']],[600,1000,1200,999,1000,1100,1200])
  self.assertTrue(all(r['entity']['departmentId']==CHILD_ID for r in body['series']))
  self.assertNotIn('privateNote',response.text);self.assertNotIn('Peer',response.text)
  self.assertLessEqual(len(sql),16,'Range is batched, not one SQL round trip per day')
  self.assertTrue(all(s.lstrip().split()[0].upper() in ('SELECT','PRAGMA') for s in sql))
  print(f'DAILY_INDICATOR_RANGE days=7 sql={len(sql)} bytes={len(response.content)} writes=0')
 def test_missing_middle_day_is_present_not_zero(self):
  with self.factory.begin() as db:self.add_day(db,10,1500)
  response=self.get(current_date='2026-10-10',baseline_date='2026-10-07');self.assertEqual(response.status_code,200,response.text)
  rows=response.json()['series'];self.assertEqual([r['reportDate'] for r in rows],['2026-10-07','2026-10-08','2026-10-09','2026-10-10'])
  self.assertEqual(rows[2]['state'],'missing');self.assertIsNone(rows[2]['entity'])
 def test_preceding_day_anchors_first_delta_same_period_unit(self):
  with self.factory.begin() as db:self.add_day(db,6,800)
  self.agency();body=self.get(current_date='2026-10-08',baseline_date='2026-10-07').json()
  self.assertEqual(body['preceding']['reportDate'],'2026-10-06')
  self.assertEqual(body['preceding']['state'],'available')
  self.assertEqual(body['preceding']['entity']['departmentId'],CHILD_ID)
  self.assertEqual(body['preceding']['entity']['parameters']['totalDossierOnlinePaymentSuccess'],800)
  self.assertEqual([r['reportDate'] for r in body['series']],['2026-10-07','2026-10-08'])
  self.assertNotIn('privateNote',str(body));self.assertNotIn('Peer',str(body))
 def test_preceding_missing_and_before_supported_history_remains_missing(self):
  body=self.get().json();self.assertEqual(body['preceding']['reportDate'],'2026-10-06')
  self.assertEqual(body['preceding']['state'],'missing');self.assertIsNone(body['preceding']['entity'])
  with self.factory.begin() as db:self.add_day(db,6,800)
  body=self.get(baseline_date='2026-10-06').json()
  self.assertEqual(body['preceding']['reportDate'],'2026-10-05');self.assertIsNone(body['preceding']['entity'])
 def test_provincial_middle_and_preceding_score_use_linked_national_source(self):
  with self.factory.begin() as db:
   self.add_day(db,6,800);self.add_day(db,9,1300)
   for entity in db.scalars(select(Entity).join(Dataset).where(Dataset.group_name=='transparency',Entity.entity_kind=='root')):
    entity.api_score=99
  body=self.get(unit_id=ROOT_ID,group='transparency',baseline_date='2026-10-07',current_date='2026-10-09').json()
  self.assertEqual(body['preceding']['entity']['apiScore'],2)
  self.assertEqual(body['series'][1]['entity']['apiScore'],2)
  self.assertEqual(body['series'][1]['entity']['scoreSource'],'dvcqg-national-summary')
 def test_leap_year_range_is_bounded_without_data(self):
  from qd766.backend.daily_indicators import comparison_payload
  from qd766.periods import PeriodSelection
  with self.factory() as db:
   body=comparison_payload(db,uuid.UUID(ROOT_ID),uuid.UUID(CHILD_ID),PeriodSelection('year',2028,None),
    'transparency',date(2028,12,31),date(2028,1,1))
  self.assertEqual(len(body['series']),366);self.assertEqual(body['series'][59]['reportDate'],'2028-02-29')
  self.assertTrue(all(r['entity'] is None for r in body['series']))
 def test_default_pair_is_latest_and_calendar_previous_day(self):
  response=self.get();self.assertEqual(response.status_code,200,response.text);body=response.json()
  self.assertEqual(body['current']['reportDate'],'2026-10-08');self.assertEqual(body['baseline']['reportDate'],'2026-10-07')
  self.assertEqual(body['availableDates'],['2026-10-08','2026-10-07'])
  self.assertEqual(body['baseline']['entity']['parameters']['totalDossierOnlinePaymentSuccess'],1000)
  self.assertEqual(body['current']['entity']['parameters']['totalDossierFinancialObligation'],1400)
  self.assertEqual(body['unitId'],CHILD_ID);self.assertNotIn('private',response.text)
  self.assertNotIn('sensitiveNote',response.text);self.assertNotIn('12345',response.text)
  self.assertNotIn('raw',body['current']);self.assertNotIn('snapshotId',body['current'])
 def test_new_cache_is_bounded_and_does_not_change_dashboard_cache(self):
  self.assertEqual(self.app.state.daily_indicator_cache.max_entries,64)
  self.assertIsNone(self.app.state.dashboard_cache.max_entries)
  before=self.app.state.dashboard_cache.stats()
  self.assertEqual(self.get().status_code,200)
  self.assertEqual(self.app.state.dashboard_cache.stats(),before)
  self.assertEqual(self.app.state.daily_indicator_cache.stats().entries,1)
 def test_missing_previous_day_does_not_fall_back(self):
  with self.factory.begin() as db:
   record=db.scalar(select(DailyObservation).where(DailyObservation.report_date==date(2026,10,8)))
   record.report_date=date(2026,10,9)
  body=self.get().json()
  self.assertEqual(body['current']['reportDate'],'2026-10-09');self.assertEqual(body['baseline']['reportDate'],'2026-10-08')
  self.assertEqual(body['baseline']['state'],'missing');self.assertIsNone(body['baseline']['entity'])
  body=self.get(current_date='2026-10-09',baseline_date='2026-10-07').json()
  self.assertEqual(body['baseline']['entity']['parameters']['totalDossierOnlinePaymentSuccess'],1000)
 def test_validation_and_formality_blocked(self):
  for changes in ({'current_date':'bad'},{'baseline_date':'2026-09-07'},
    {'current_date':'2026-10-07','baseline_date':'2026-10-07'},
    {'current_date':'2026-10-07','baseline_date':'2026-10-08'},
    {'group':'unknown'},{'period_type':'quarter','period_value':5}):
   response=self.get(**changes);self.assertEqual(response.status_code,422,response.text)
  self.assertEqual(self.get(scope='formality').status_code,403)
  self.assertEqual(self.get(formality_id=str(uuid.uuid4())).status_code,403)
  self.assertEqual(self.client.post('/api/v1/dashboard/daily-indicator-comparison',json=self.query).status_code,403)
 def test_agency_cache_isolation_province_and_unit_boundary(self):
  self.assertEqual(self.get(unit_id=str(self.fixture.peer)).status_code,200) # Province account primes another unit's cache.
  self.agency();response=self.get();self.assertEqual(response.status_code,200,response.text)
  for unit in (ROOT_ID,str(self.fixture.peer)):
   self.assertEqual(self.get(unit_id=unit).status_code,403)
  self.assertEqual(self.get(root_department_id=str(uuid.uuid4())).status_code,403)
  self.client.cookies.clear();self.assertEqual(self.get().status_code,401)
 def test_unit_must_actually_belong_to_root(self):
  with self.factory.begin() as db:db.get(UserAccount,self.fixture.user).role='admin'
  self.assertEqual(self.get(root_department_id=str(uuid.uuid4())).status_code,403)
 def test_selected_unit_and_group_only_no_writes(self):
  response=self.get(group='transparency',current_date='2026-10-08',baseline_date='2026-10-07')
  self.assertEqual(response.status_code,200,response.text);body=response.json()
  self.assertTrue(body['current']['entity']['metrics']);self.assertEqual(body['current']['entity']['parameters'],{})
  self.assertEqual(body['group'],'transparency');self.assertNotIn('datasets',body)
  self.assertNotIn('children',response.text);self.assertNotIn('Peer',response.text)
  with self.factory() as db:
   self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
   self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)
   self.assertEqual(db.scalar(select(func.count()).select_from(Snapshot)),2)
 def test_province_group_score_uses_same_days_national_summary(self):
  with self.factory.begin() as db:
   root=db.scalar(select(Entity).join(Dataset).where(Dataset.snapshot_id==self.fixture.ids[8],
    Dataset.group_name=='transparency',Entity.entity_kind=='root'));root.api_score=99
  response=self.get(unit_id=ROOT_ID,group='transparency');self.assertEqual(response.status_code,200,response.text)
  self.assertEqual(response.json()['current']['entity']['apiScore'],2)
  self.assertEqual(response.json()['current']['entity']['scoreSource'],'dvcqg-national-summary')
 def test_empty_period_and_explicit_missing_day_are_not_latest(self):
  body=self.get(period_value=9).json();self.assertEqual(body['availableDates'],[]);self.assertIsNone(body['current']['entity'])
  body=self.get(current_date='2026-10-12',baseline_date='2026-10-11').json()
  self.assertEqual(body['current']['state'],'missing');self.assertIsNone(body['current']['entity'])
 def test_default_baseline_does_not_cross_reporting_period(self):
  with self.factory.begin() as db:
   for day in (7,8):
    record=db.scalar(select(DailyObservation).where(DailyObservation.report_date==date(2026,10,day)))
    record.report_date=date(2026,11,1 if day==8 else 2)
    record.period_value=11;record.snapshot.period_value=11
   # Restrict to 01/11, deliberately no 31/10 in this period.
   db.flush()
   record=db.scalar(select(DailyObservation).where(DailyObservation.report_date==date(2026,11,2)));db.delete(record)
  from qd766.backend.daily_indicators import comparison_payload
  from qd766.periods import PeriodSelection
  with self.factory() as db:
   body=comparison_payload(db,uuid.UUID(ROOT_ID),uuid.UUID(CHILD_ID),PeriodSelection('month',2026,11),'formality-online-payment-tree')
  self.assertEqual(body['current']['reportDate'],'2026-11-01')
  self.assertEqual(body['baseline']['state'],'outside-period');self.assertIsNone(body['baseline']['entity'])
 def test_read_cost_is_bounded_and_cached(self):
  self.agency();sql=[];latency=[];engine=self.app.state.engine
  counter=lambda *args:sql.append(args[2])
  event.listen(engine,'before_cursor_execute',counter)
  try:
   start=time.perf_counter();response=self.get();cold_ms=(time.perf_counter()-start)*1000
   self.assertEqual(response.status_code,200,response.text);cold_sql=len(sql)
   self.assertLessEqual(cold_sql,16)
   for _ in range(100):
    before=len(sql);start=time.perf_counter();response=self.get()
    latency.append((time.perf_counter()-start)*1000)
    self.assertEqual(response.status_code,200,response.text)
    self.assertLessEqual(len(sql)-before,6)
   self.assertTrue(all(statement.lstrip().split()[0].upper() in ('SELECT','PRAGMA') for statement in sql),'Read path must not write')
  finally:event.remove(engine,'before_cursor_execute',counter)
  print('DAILY_INDICATOR_LOCAL_READS=100 cold_ms=%.2f cold_sql=%d warm_p95_ms=%.2f warm_sql=%.1f response_bytes=%d'%(
   cold_ms,cold_sql,sorted(latency)[94],(len(sql)-cold_sql)/100,len(response.content)))
