import unittest,uuid
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import test_challenges
from qd766.backend.models import CreditLedgerEntry,UserAccount

class PersonalCreditPageTests(unittest.TestCase):
 def setUp(self):
  self.f=test_challenges.ChallengeTests();self.f.setUp()
  self.f.app.state.settings=replace(self.f.app.state.settings,paid_requests_enabled=True,trial_credits_enabled=True)
  with self.f.factory.begin() as db:
   for user,count in [(0,31),(1,5)]:
    for i in range(count):
     db.add(CreditLedgerEntry(account_id=self.f.ids[user],event_key=str(uuid.uuid4()),entry_type='charge',amount=5,
      available_delta=-5,reserved_delta=0,available_after=i,reserved_after=0,
      created_at=datetime(2026,10,11,tzinfo=timezone.utc)+timedelta(seconds=i)))
 def tearDown(self):self.f.tearDown()
 def test_fifteen_per_page_private_and_read_only(self):
  values=[]
  for offset,count in [(0,15),(15,15),(30,1)]:
   response=self.f.client.get('/api/v1/me/credits',params={'offset':offset,'limit':15})
   self.assertEqual(response.status_code,200,response.text);body=response.json()
   self.assertEqual(len(body['items']),count);self.assertEqual(body['total'],31)
   self.assertEqual(body['accessTier'],'agency');self.assertEqual(body['role'],'user')
   self.assertEqual(body['availableCredits'],111);values.extend(row['availableAfter'] for row in body['items'])
  self.assertEqual(values,list(reversed(range(31))))
  with self.f.factory() as db:self.assertEqual(db.get(UserAccount,self.f.ids[0]).credit_balance,111)
  self.f.login(1);self.assertEqual(self.f.client.get('/api/v1/me/credits?limit=15').json()['total'],5)
  self.f.login(None);self.assertEqual(self.f.client.get('/api/v1/me/credits?limit=15').status_code,401)
