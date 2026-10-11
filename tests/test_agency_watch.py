import unittest,uuid,time,statistics
from tempfile import TemporaryDirectory
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select,func,event,create_engine
from sqlalchemy.orm import sessionmaker
import test_challenges
from qd766.backend.models import Base,AgencyWatchPreference,Entity,Dataset,Department,UserAccount,LoginSession
class WatchTests(unittest.TestCase):
 def setUp(self):
  self.f=test_challenges.ChallengeTests();self.f.setUp()
  with self.f.factory.begin() as db:
   s=self.f.snapshot(db)
   dataset=db.scalar(select(Dataset).where(Dataset.snapshot_id==s.id).limit(1))
   for i in range(2,8):
    db.add(Entity(dataset_id=dataset.id,department_id=self.f.units[i],entity_kind='child',position=i,
     api_score=10,api_max_score=18,score_source='source'))
 def tearDown(self):self.f.tearDown()
 def read(self,client=None,root=None):
  return (client or self.f.client).get('/api/v1/me/agency-watch',params={'province_id':str(root or self.f.root)})
 def save(self,indices,**extra):
  return self.f.client.post('/api/v1/me/agency-watch',headers=self.f.headers,json={
   'provinceId':str(self.f.root),'unitIds':[str(self.f.units[i]) for i in indices],**extra})
 def test_cross_device_same_account_isolation_and_no_billing(self):
  r=self.save([1,2,3,4,5]);self.assertEqual(r.status_code,200,r.text)
  with TestClient(self.f.app,base_url='https://testserver') as second:
   second.cookies.set('qd766_session','duel-0')
   self.assertEqual(self.read(second).json(),r.json())
   self.assertEqual(self.read(second).headers['cache-control'],'no-store')
  self.f.login(1);self.assertEqual(self.read().json(),{'unitIds':[]})
  self.f.login(0);self.assertEqual(self.save([2]).status_code,200)
  self.assertEqual(self.read().json()['unitIds'],[str(self.f.units[2])])
  with self.f.factory() as db:
   self.assertEqual(db.scalar(select(func.count()).select_from(AgencyWatchPreference)),1)
   self.assertTrue(all(a.credit_balance==111 and a.credit_reserved==0 for a in db.scalars(select(UserAccount))))
 def test_validation_auth_csrf_scope_and_clear(self):
  self.assertEqual(self.save([1]*2).status_code,422)
  self.assertEqual(self.save([1,2,3,4,5,6]).status_code,422)
  self.assertEqual(self.save([0]).status_code,422)
  self.assertEqual(self.save([1],accountId=str(self.f.ids[1])).status_code,422)
  self.assertEqual(self.save([1],provinceId=str(uuid.uuid4())).status_code,403)
  self.assertEqual(self.read(root=uuid.uuid4()).status_code,403)
  self.f.headers={};self.assertEqual(self.save([1]).status_code,403);self.f.headers={'X-QD766-CSRF':'csrf'}
  self.f.login(8);self.assertEqual(self.read().status_code,403)
  self.f.login(None);self.assertEqual(self.read().status_code,401)
  self.f.login(0);self.assertEqual(self.save([]).status_code,200);self.assertEqual(self.read().json(),{'unitIds':[]})
 def test_bounded_read_queries_and_local_latency(self):
  self.assertEqual(self.save([1,2,3,4,5]).status_code,200)
  queries=[];latency=[]
  def count(*args):queries.append(1)
  event.listen(self.f.app.state.engine,'before_cursor_execute',count)
  try:
   for _ in range(100):
    before=len(queries);start=time.perf_counter();r=self.read()
    latency.append((time.perf_counter()-start)*1000)
    self.assertEqual(r.status_code,200);self.assertLessEqual(len(queries)-before,6)
  finally:event.remove(self.f.app.state.engine,'before_cursor_execute',count)
  print('WATCH_LOCAL_READS=100 p95_ms=%.2f sql_per_read=%.1f'%(sorted(latency)[94],len(queries)/100))
 def test_simultaneous_read_sessions_keep_account_isolation(self):
  self.assertEqual(self.save([1,2]).status_code,200)
  def browser(index):
   times=[]
   with TestClient(self.f.app,base_url='https://testserver') as client:
    client.cookies.set('qd766_session','duel-'+str(index))
    for _ in range(20):
     start=time.perf_counter();r=self.read(client);times.append((time.perf_counter()-start)*1000)
     self.assertEqual(r.status_code,200,r.text)
     self.assertEqual(r.json()['unitIds'],[str(self.f.units[i]) for i in [1,2]] if index==0 else [])
   return times
  # Separate pooled connections are required for concurrency tests. The normal
  # in-memory fixture uses one StaticPool connection and is intentionally serial.
  original_engine=self.f.app.state.engine;original_factory=self.f.app.state.session_factory
  with TemporaryDirectory(prefix='.tmp-watch-load-',dir=Path(__file__).resolve().parents[1]) as temp:
   engine=create_engine('sqlite:///'+str(Path(temp)/'load.sqlite'),connect_args={'check_same_thread':False})
   Base.metadata.create_all(engine)
   with original_engine.connect() as source,engine.begin() as target:
    for model in [Department,UserAccount,LoginSession,AgencyWatchPreference]:
     rows=[dict(row) for row in source.execute(select(model.__table__)).mappings()]
     if rows:target.execute(model.__table__.insert(),rows)
   self.f.app.state.engine=engine;self.f.app.state.session_factory=sessionmaker(bind=engine,expire_on_commit=False)
   try:
    start=time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as executor:
     times=[value for group in executor.map(browser,range(8)) for value in group]
    elapsed=time.perf_counter()-start
   finally:
    self.f.app.state.engine=original_engine;self.f.app.state.session_factory=original_factory;engine.dispose()
  print('WATCH_CONCURRENT_LOCAL sessions=8 reads=160 errors=0 p95_ms=%.2f requests_per_second=%.1f'%(sorted(times)[151],160/elapsed))
