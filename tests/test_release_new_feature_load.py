import unittest,time,uuid,importlib.util,io
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
from sqlalchemy import event,select,func,inspect
from alembic.migration import MigrationContext
from alembic.operations import Operations
import test_challenges
from qd766.backend.models import AgencyChallenge,AgencyWatchPreference,UserAccount,Department
class ReleaseLoadTests(unittest.TestCase):
 def setUp(self):self.f=test_challenges.ChallengeTests();self.f.setUp()
 def tearDown(self):self.f.tearDown()
 def test_challenge_bounded_queries_large_history(self):
  with self.f.factory.begin() as db:
   for state,start,count in [('finished',2000,500),('pending',3000,500)]:
    for i in range(count):
     db.add(AgencyChallenge(sender_id=self.f.ids[1],recipient_id=self.f.ids[0],
       root_department_id=self.f.root,sender_unit_id=self.f.units[1],recipient_unit_id=self.f.units[0],
       pair_key=':'.join(sorted([str(self.f.ids[0]),str(self.f.ids[1])])),period_type='year',year=start+i,period_key=0,
       state=state,sender_score=Decimal('54') if state=='finished' else None,
       recipient_score=Decimal('60') if state=='finished' else None,created_at=datetime(2026,10,11,tzinfo=timezone.utc)))
  sql=[];event.listen(self.f.app.state.engine,'before_cursor_execute',counter:=lambda *a:sql.append(1))
  try:
   for path,limit in [('/incoming',20),('/board',10),('',10),('/board?status=finished&page=50',10),('/directory',None)]:
    times=[];counts=[]
    for _ in range(20):
     before=len(sql);start=time.perf_counter();r=self.f.client.get('/api/v1/me/challenges'+path)
     times.append((time.perf_counter()-start)*1000);counts.append(len(sql)-before)
     self.assertEqual(r.status_code,200,r.text)
     if limit:self.assertEqual(len(r.json()['items']),limit)
     self.assertLessEqual(counts[-1],10,'No per-row SQL (N+1)')
    if path=='/incoming':self.assertEqual(r.json()['count'],500)
    if path=='/board':self.assertEqual(r.json()['players'][0]['points'],1500)
    print('CHALLENGE_LOCAL_%s p95_ms=%.2f max_sql=%d bytes=%d'%(path or 'listing',sorted(times)[18],max(counts),len(r.content)))
  finally:event.remove(self.f.app.state.engine,'before_cursor_execute',counter)
 def test_challenge_pagination_order_scope_and_status(self):
  with self.f.factory.begin() as db:
   for state in ['accepted','finished']:
    for i in range(23):
     db.add(AgencyChallenge(sender_id=self.f.ids[0],recipient_id=self.f.ids[1],root_department_id=self.f.root,
      sender_unit_id=self.f.units[0],recipient_unit_id=self.f.units[1],pair_key='own',period_type='year',
      year=(3000 if state=='accepted' else 2000)+i,period_key=0,state=state,
      created_at=datetime(2026,10,11,tzinfo=timezone.utc)+test_challenges.timedelta(seconds=i)))
   other=Department(id=uuid.uuid4(),name='Other province');db.add(other);db.flush()
   db.add(AgencyChallenge(sender_id=self.f.ids[2],recipient_id=self.f.ids[3],root_department_id=other.id,
    sender_unit_id=self.f.units[2],recipient_unit_id=self.f.units[3],pair_key='foreign',period_type='year',year=2027,period_key=0,state='accepted'))
  for path,total in [('',46),('/board?status=active',23),('/board?status=finished',23)]:
   ids=[];dates=[]
   for page in range(1,(total+9)//10+1):
    r=self.f.client.get('/api/v1/me/challenges'+path+('&' if '?' in path else '?')+'page='+str(page))
    self.assertEqual(r.status_code,200,r.text);body=r.json()
    self.assertEqual(body['pageSize'],10);self.assertEqual(body['page'],page);self.assertEqual(body['total'],total)
    self.assertEqual(len(body['items']),min(10,total-(page-1)*10))
    ids.extend(k['id'] for k in body['items']);dates.extend(k['createdAt'] for k in body['items'])
    if 'status=active' in path:self.assertTrue(all(k['state']=='accepted' for k in body['items']))
    if 'status=finished' in path:self.assertTrue(all(k['state']=='finished' for k in body['items']))
   self.assertEqual(len(set(ids)),total);self.assertEqual(dates,sorted(dates,reverse=True))
  self.assertEqual(self.f.client.get('/api/v1/me/challenges?page=0').status_code,422)
  self.assertEqual(self.f.client.get('/api/v1/me/challenges/board?status=invalid').status_code,422)
  self.assertEqual(self.f.client.get('/api/v1/me/challenges?page=999').json()['page'],5)
  self.f.login(4);self.assertEqual(self.f.client.get('/api/v1/me/challenges').json()['total'],0)
  self.f.login(None);self.assertEqual(self.f.client.get('/api/v1/me/challenges?page=2').status_code,401)
 def test_new_migrations_sqlite_and_postgres_ddl_no_existing_data_changes(self):
  modules=[]
  for file in ['20261011_0026_agency_challenges.py','20261011_0027_agency_watch.py']:
   path=Path(__file__).resolve().parents[1]/'alembic/versions'/file
   spec=importlib.util.spec_from_file_location(file[:-3],path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules.append(module)
  with self.f.app.state.engine.begin() as connection:
   AgencyWatchPreference.__table__.drop(connection);AgencyChallenge.__table__.drop(connection)
   operations=Operations(MigrationContext.configure(connection))
   for module in modules:module.op=operations;module.upgrade()
   inspector=inspect(connection)
   self.assertIn('agency_watch_preferences',inspector.get_table_names())
   self.assertTrue({'ix_challenge_incoming','ix_challenge_board'}<={i['name'] for i in inspector.get_indexes('agency_challenges')})
   self.assertEqual(connection.scalar(select(func.count()).select_from(UserAccount)),9)
   self.assertEqual(connection.scalar(select(func.count()).select_from(Department)),10)
  output=io.StringIO();operations=Operations(MigrationContext.configure(dialect_name='postgresql',opts={'as_sql':True,'output_buffer':output}))
  for module in modules:module.op=operations;module.upgrade()
  sql=output.getvalue();self.assertIn('JSONB',sql);self.assertIn('PRIMARY KEY (account_id, root_department_id)',sql)
  self.assertNotIn('DROP ',sql);self.assertNotIn('UPDATE user_accounts',sql)
  print('NEW_MIGRATIONS=PASS SQLite execution + PostgreSQL DDL; existing accounts/departments unchanged')
