import sys,unittest,uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from fastapi.testclient import TestClient
from sqlalchemy import select
from qd766.backend import create_app
from qd766.backend.config import Settings
from qd766.backend.auth import digest
from qd766.backend.models import Base,UserAccount,LoginSession,Department,AgencyChallenge,Snapshot,Dataset,Entity
from qd766.backend.challenges import settle_snapshot

NOW=datetime(2026,10,11,5,tzinfo=timezone.utc)

class ChallengeTests(unittest.TestCase):
 def setUp(self):
  self.app=create_app(Settings(database_url='sqlite+pysqlite://',public_read_only=True,require_login=True,invite_required=True,
   google_client_id='test',google_client_secret='secret',google_redirect_uri='https://testserver/api/v1/auth/google/callback'))
  Base.metadata.create_all(self.app.state.engine);self.client=TestClient(self.app,base_url='https://testserver')
  self.factory=self.app.state.session_factory;self.root=uuid.uuid4();self.ids={};self.units={}
  with self.factory.begin() as db:
   db.add(Department(id=self.root,name='Tỉnh mẫu'));db.flush()
   for i in range(9):
    unit=Department(id=uuid.uuid4(),name='Xã '+str(i));db.add(unit);db.flush();self.units[i]=unit.id
    a=UserAccount(external_subject='duel-'+str(i),display_name='Người '+str(i),email='private@example.invalid',
      access_tier='agency',unit_department_id=unit.id,root_department_id=self.root,trial_admitted=i!=8,
      active=True,credit_balance=111)
    db.add(a);db.flush();self.ids[i]=a.id
    db.add(LoginSession(token_hash=digest('duel-'+str(i)),account_id=a.id,csrf_token='csrf',
      expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
  self.headers={'X-QD766-CSRF':'csrf'};self.clock=patch('qd766.backend.challenges.now_utc',return_value=NOW);self.clock.start();self.login(0)
 def tearDown(self):
  self.clock.stop();self.client.close();self.app.state.engine.dispose()
 def login(self,i):
  self.client.cookies.clear()
  if i is not None:self.client.cookies.set('qd766_session','duel-'+str(i))
 def send(self,i=1,kind='month',value=10,year=2026):
  return self.client.post('/api/v1/me/challenges',headers=self.headers,json={
   'recipientId':str(self.ids[i]),'periodType':kind,'year':year,'periodValue':value})
 def test_directory_privacy_and_auth_csrf_cross_province(self):
  r=self.client.get('/api/v1/me/challenges/directory');self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(len(r.json()['agencies']),7);self.assertNotIn('email',r.text);self.assertNotIn('private',r.text)
  self.assertEqual(r.headers['cache-control'],'no-store')
  self.headers={};self.assertEqual(self.send().status_code,403);self.headers={'X-QD766-CSRF':'csrf'}
  with self.factory.begin() as db:
   root=Department(id=uuid.uuid4(),name='Tỉnh khác');db.add(root);db.flush()
   db.get(UserAccount,self.ids[7]).root_department_id=root.id
  self.assertEqual(self.send(7).status_code,403);self.assertEqual(self.send(8).status_code,403)
  self.login(None);self.assertEqual(self.client.get('/api/v1/me/challenges/board').status_code,401)
 def test_future_periods_duplicate_reverse_and_acceptance_authorization(self):
  self.assertEqual(self.send(value=9).status_code,422)
  self.assertEqual(self.send(value=13).status_code,422)
  self.assertEqual(self.send(kind='year',value=1).status_code,422)
  r=self.send(value=11);self.assertEqual(r.status_code,200,r.text);cid=r.json()['id']
  self.assertEqual(self.send(value=11).status_code,409)
  self.login(1);reverse=self.send(0,value=11);self.assertEqual(reverse.status_code,409)
  self.assertEqual(reverse.json()['detail'],'Đã có kèo thách đấu giữa hai tài khoản trong kỳ báo cáo chưa kết thúc này.')
  self.login(2);self.assertEqual(self.client.post('/api/v1/me/challenges/'+cid+'/answer',headers=self.headers,json={'action':'accept'}).status_code,404)
  self.login(1);accepted=self.client.post('/api/v1/me/challenges/'+cid+'/answer',headers=self.headers,json={'action':'accept'})
  self.assertEqual(accepted.json()['state'],'accepted');self.assertEqual(self.client.post('/api/v1/me/challenges/'+cid+'/answer',headers=self.headers,json={'action':'accept'}).status_code,409)
  self.assertEqual(self.send(0,value=11).status_code,409)
  self.assertEqual(self.send(0,value=12).status_code,200,'Same opponent, different unfinished period is allowed')
 def test_incoming_private_notification_accept_decline_and_expiry(self):
  r=self.send();cid=r.json()['id']
  self.assertEqual(self.client.get('/api/v1/me/challenges/incoming').json()['count'],0)
  self.login(2);self.assertEqual(self.client.get('/api/v1/me/challenges/incoming').json()['count'],0)
  self.login(1);incoming=self.client.get('/api/v1/me/challenges/incoming')
  self.assertEqual(incoming.status_code,200,incoming.text);self.assertEqual(incoming.headers['cache-control'],'no-store')
  self.assertEqual(incoming.json()['count'],1);self.assertTrue(incoming.json()['items'][0]['canAnswer'])
  self.assertNotIn('email',incoming.text)
  with patch('qd766.backend.challenges.now_utc',return_value=datetime(2026,11,1,tzinfo=timezone.utc)):
   self.assertEqual(self.client.get('/api/v1/me/challenges/incoming').json()['count'],0)
  self.client.post('/api/v1/me/challenges/'+cid+'/answer',headers=self.headers,json={'action':'decline'})
  self.assertEqual(self.client.get('/api/v1/me/challenges/incoming').json()['count'],0)
  self.login(None);self.assertEqual(self.client.get('/api/v1/me/challenges/incoming').status_code,401)
 def test_five_distinct_opponents_multiple_periods_and_no_credit_changes(self):
  for i in range(1,6):self.assertEqual(self.send(i).status_code,200)
  self.assertEqual(self.send(6).status_code,409)
  self.assertEqual(self.send(1,value=11).status_code,200)
  self.assertEqual(self.send(1,kind='quarter',value=4).status_code,200)
  self.assertEqual(self.send(1,kind='year',value=None).status_code,200)
  with self.factory() as db:
   self.assertTrue(all(a.credit_balance==111 and a.credit_reserved==0 for a in db.scalars(select(UserAccount))))
 def snapshot(self,db,score_a=Decimal('10'),score_b=Decimal('9'),missing=False,captured=None):
  s=Snapshot(snapshot_key=str(uuid.uuid4()),schema_version=1,root_department_id=self.root,
   period_type='month',year=2026,period_value=10,scope='all',state='complete',
   created_at=captured or datetime(2026,11,1,2,tzinfo=timezone.utc))
  db.add(s);db.flush()
  groups=['transparency','dvc-progress-tree','provide-online-tree','dossier-digitized','handling-satisfaction','formality-online-payment-tree']
  for pos,(group,maximum) in enumerate(zip(groups,[18,20,12,22,18,10])):
   d=Dataset(snapshot_id=s.id,position=pos,group_name=group,schema_kind='parameters',formula_status='source',
    score_policy='source',raw_path='',raw_sha256='0'*64);db.add(d);db.flush()
   for i,score in [(0,score_a),(1,score_b)]:
    db.add(Entity(dataset_id=d.id,department_id=self.units[i],entity_kind='child',position=i,
     api_score=None if missing and pos==5 and i==1 else score,api_max_score=maximum,score_source='source'))
  db.flush();return s
 def accepted(self):
  r=self.send();self.assertEqual(r.status_code,200,r.text)
  self.login(1);self.client.post('/api/v1/me/challenges/'+r.json()['id']+'/answer',headers=self.headers,json={'action':'accept'})
  return uuid.UUID(r.json()['id'])
 def settle(self,db,snapshot):
  with patch('qd766.backend.challenges.now_utc',return_value=datetime(2026,11,1,3,tzinfo=timezone.utc)):
   return settle_snapshot(db,snapshot)
 def test_settlement_closed_complete_shared_snapshot_immutable_and_board(self):
  cid=self.accepted()
  with self.factory.begin() as db:
   current=self.snapshot(db,captured=NOW);self.assertEqual(self.settle(db,current),0)
   missing=self.snapshot(db,missing=True);self.assertEqual(self.settle(db,missing),0)
   good=self.snapshot(db);self.assertEqual(self.settle(db,good),1)
   k=db.get(AgencyChallenge,cid);self.assertEqual(k.sender_score,60);self.assertEqual(k.recipient_score,54)
   self.assertEqual(k.result_snapshot_id,good.id);self.assertEqual(self.settle(db,self.snapshot(db,Decimal('8'),Decimal('10'))),0)
  board=self.client.get('/api/v1/me/challenges/board');self.assertEqual(board.status_code,200,board.text)
  self.assertEqual(board.json()['players'][0]['points'],3);self.assertEqual(board.json()['players'][1]['points'],0)
  self.assertNotIn('email',board.text)
 def test_draw_decline_and_expired_acceptance(self):
  cid=self.accepted()
  with self.factory.begin() as db:self.assertEqual(self.settle(db,self.snapshot(db,Decimal('9'),Decimal('9'))),1)
  board=self.client.get('/api/v1/me/challenges/board').json()
  self.assertEqual([p['points'] for p in board['players']],[1,1]);self.assertIsNone(board['items'][0]['winnerId'])
  self.login(0);r=self.send(2,value=11);cid=r.json()['id'];self.login(2)
  self.assertEqual(self.client.post('/api/v1/me/challenges/'+cid+'/answer',headers=self.headers,json={'action':'decline'}).json()['state'],'declined')
  self.login(0);r=self.send(3,value=12);cid=r.json()['id'];self.login(3)
  with patch('qd766.backend.challenges.now_utc',return_value=datetime(2027,1,1,tzinfo=timezone.utc)):
   self.assertEqual(self.client.post('/api/v1/me/challenges/'+cid+'/answer',headers=self.headers,json={'action':'accept'}).status_code,409)
   self.assertEqual(self.client.get('/api/v1/me/challenges').json()['items'][0]['state'],'expired')
