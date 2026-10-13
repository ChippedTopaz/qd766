import unittest,uuid,copy
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,func,event
import test_trial_admin
from test_backend import ROOT_ID,CHILD_ID,TAY_NINH_ROOT_ID,TAY_NINH_CHILD_ID
from qd766.backend.models import UserAccount,AdminAudit

class AdminAccountPaginationTests(unittest.TestCase):
 def setUp(self):
  self.f=test_trial_admin.TrialAdminTests();self.f.setUp()
  with self.f.app.state.session_factory.begin() as db:
   for i in range(520):
    db.add(UserAccount(external_subject='page-user-'+str(i),display_name='Page User %04d'%i,
     email='user%04d@example.test'%i,active=i%3!=2,trial_admitted=i%3!=1,access_tier='agency',
     root_department_id=uuid.UUID(ROOT_ID if i%2==0 else TAY_NINH_ROOT_ID),
     unit_department_id=uuid.UUID(CHILD_ID if i%2==0 else TAY_NINH_CHILD_ID),credit_balance=37,
     created_at=datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(seconds=i)))
 def tearDown(self):self.f.tearDown()
 def get(self,**params):return self.f.client.get('/api/v1/admin/accounts',params=params)
 def test_all_pages_beyond_500_and_stable_latest_order(self):
  ids=[]
  for page in range(1,54):
   response=self.get(page=page);self.assertEqual(response.status_code,200,response.text);body=response.json()
   self.assertEqual(body['total'],521);self.assertEqual(body['totalAll'],521);self.assertEqual(body['pageSize'],10)
   self.assertEqual(body['page'],page);self.assertEqual(len(body['items']),10 if page<53 else 1)
   ids.extend(a['id'] for a in body['items'])
  self.assertEqual(len(set(ids)),521)
  with self.f.app.state.session_factory() as db:
   expected=[str(i) for i in db.scalars(select(UserAccount.id).order_by(UserAccount.created_at.desc(),UserAccount.id.desc()))]
   self.assertEqual(ids,expected)
  self.assertEqual(len(self.get().json()),500,'Existing Credit-management array contract unchanged')
  self.assertEqual(self.get(page=999).json()['page'],53)
 def test_status_counts_search_combination_and_full_unit_options(self):
  statuses={}
  for state in ['active','unadmitted','locked']:
   body=self.get(page=1,status=state).json();statuses[state]=body['total']
   self.assertEqual(body['totalAll'],521)
   for a in body['items']:
    self.assertTrue(not a['active'] if state=='locked' else a['active'] and a['admitted']==(state=='active'))
  self.assertEqual(sum(statuses.values()),521)
  body=self.get(page=1,search='user0510@example.test',status='active',provinceId=ROOT_ID,unitId=CHILD_ID).json()
  self.assertEqual(body['total'],1);self.assertEqual(body['items'][0]['name'],'Page User 0510')
  self.assertEqual(body['units'],[{'id':CHILD_ID,'name':'Văn phòng UBND'}])
  self.assertEqual(self.get(page=1,search='%',provinceId=ROOT_ID).json()['total'],0,'Search treats SQL wildcard literally')
  empty=self.get(page=4,status='locked',search='does-not-exist').json()
  self.assertEqual(empty['page'],1);self.assertEqual(empty['items'],[]);self.assertEqual(empty['total'],0)
  self.assertGreater(self.get(page=1,search='Văn phòng UBND',provinceId=ROOT_ID).json()['total'],100,'Search agency names across all pages')
  self.assertEqual(self.get(page=1,provinceId=ROOT_ID,unitId=TAY_NINH_CHILD_ID).json()['total'],0)
 def test_validation_and_admin_only(self):
  for params in ({'page':0},{'status':'unknown','page':1},{'page':1,'search':'x'*201},{'page':1,'provinceId':'bad'}):
   self.assertEqual(self.get(**params).status_code,422)
  self.f.client.cookies.clear();self.assertEqual(self.get(page=1).status_code,401)
  self.f.client.cookies.set('qd766_session','owner-token')
  with self.f.app.state.session_factory.begin() as db:db.get(UserAccount,self.f.admin_id).role='user'
  self.assertEqual(self.get(page=1,status='locked').status_code,403)
 def test_read_only_bounded_queries_and_existing_actions_fields(self):
  sql=[];engine=self.f.app.state.engine;counter=lambda *a:sql.append(a[2]);event.listen(engine,'before_cursor_execute',counter)
  try:
   response=self.get(page=1,provinceId=ROOT_ID)
   self.assertEqual(response.status_code,200,response.text);self.assertLessEqual(len(sql),12)
   self.assertFalse(any(s.lstrip().upper().startswith(('INSERT','UPDATE','DELETE')) for s in sql))
   for a in response.json()['items']:
    for field in ('id','role','active','admitted','accessTier','credits','reservedCredits','subscription','canActivateTrial','canCollect','provinceId','unitId'):self.assertIn(field,a)
  finally:event.remove(engine,'before_cursor_execute',counter)
  with self.f.app.state.session_factory() as db:
   self.assertEqual(db.scalar(select(func.count()).select_from(AdminAudit)),0)
   self.assertTrue(all(a.credit_balance==37 for a in db.scalars(select(UserAccount).where(UserAccount.external_subject.like('page-user-%')))))
