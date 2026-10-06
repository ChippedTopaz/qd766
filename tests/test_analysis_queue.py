import unittest, uuid
from dataclasses import replace
from datetime import timedelta
from unittest.mock import patch
from sqlalchemy import select, func
import test_gemini_analysis as legacy
from qd766.backend import analysis_queue as queue
from qd766.backend.models import GeminiAnalysis, AnalysisQueueEntry, UserAccount, CreditWalletEvent, SubscriptionCycle


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.fixture=legacy.PaidAnalysisTest(); self.fixture.setUp(); self.f=self.fixture
        self.f.app.state.settings=replace(self.f.app.state.settings,gemini_queue_enabled=True)
        with self.f.factory.begin() as db:
            for aid in self.f.ids: db.get(UserAccount,aid).trial_admitted=True
    def tearDown(self): self.f.tearDown()
    def work(self,**kwargs):
        return queue.run_one(self.f.factory,self.f.app.state.settings,generate=lambda *_:self.f.evidence['findings'],**kwargs)
    def cancel(self):
        return self.f.client.post('/api/v1/me/analysis/cancel',json=self.f.body,headers={'X-QD766-CSRF':'csrf-0'})
    def event_count(self,kind):
        with self.f.factory() as db:
            return db.scalar(select(func.count()).select_from(CreditWalletEvent).where(CreditWalletEvent.kind==kind))
    def test_enqueue_replay_status_and_single_charge(self):
        queue.verify_schema(self.f.engine)
        result=self.f.post(); self.assertEqual(result.status_code,202,result.text)
        value=result.json(); self.assertEqual(value['state'],'queued'); self.assertEqual(value['heldCredits'],20)
        self.assertEqual(value['queuePosition'],1); self.f.generate.assert_not_called()
        self.assertEqual(self.f.post().json()['id'],value['id'])
        self.assertEqual(self.f.post(token=str(uuid.uuid4())).status_code,409)
        self.assertEqual(self.event_count('reserve'),1)
        self.assertEqual(self.work(),'ready'); self.assertIsNone(self.work())
        status=self.f.client.get('/api/v1/me/analysis/'+value['id']+'/status')
        self.assertEqual(status.status_code,200,status.text); self.assertEqual(status.json()['availableCredits'],92)
        self.assertEqual(self.event_count('charge'),1)
    def test_cancel_refunds_once_and_csrf(self):
        self.f.post()
        self.assertEqual(self.f.client.post('/api/v1/me/analysis/cancel',json=self.f.body).status_code,403)
        result=self.cancel(); self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['state'],'cancelled'); self.assertEqual(result.json()['availableCredits'],112)
        self.cancel(); self.assertEqual(self.event_count('refund'),1); self.assertIsNone(self.work())
    def test_status_other_account_and_capacity_before_hold(self):
        value=self.f.post().json(); self.f.client.cookies.set('qd766_session','session-1')
        self.assertEqual(self.f.client.get('/api/v1/me/analysis/'+value['id']+'/status').status_code,404)
        with patch.object(queue,'WAITING_LIMIT',1):
            result=self.f.client.post('/api/v1/me/analysis',json={**self.f.body,'token':str(uuid.uuid4())},headers={'X-QD766-CSRF':'csrf-1'})
        self.assertEqual(result.status_code,429,result.text); self.assertEqual(self.event_count('reserve'),1)
    def test_expired_wait_is_refunded_without_provider(self):
        value=self.f.post().json()
        with self.f.factory.begin() as db: db.get(AnalysisQueueEntry,uuid.UUID(value['id'])).expires_at=self.f.now-timedelta(seconds=1)
        self.assertIsNone(self.work()); self.assertEqual(self.event_count('refund'),1); self.f.generate.assert_not_called()
    def test_failure_refund_and_cancel_running_rejected(self):
        self.f.post()
        def fail(*_):
            self.assertEqual(self.cancel().status_code,409)
            raise TimeoutError('private detail')
        self.assertEqual(queue.run_one(self.f.factory,self.f.app.state.settings,generate=fail),'failed')
        self.assertEqual(self.event_count('refund'),1); self.assertEqual(self.event_count('charge'),0)
    def test_revoked_subscription_refunds_before_provider(self):
        self.f.post()
        with self.f.factory.begin() as db:
            db.scalar(select(SubscriptionCycle).where(SubscriptionCycle.account_id==self.f.ids[0])).ends_at=self.f.now-timedelta(seconds=1)
        self.assertEqual(self.work(),'refunded'); self.assertEqual(self.event_count('refund'),1)
    def test_restarted_worker_recovers_orphan_and_discards_late_result(self):
        self.f.post(); later=self.f.now+timedelta(minutes=11)
        def late(*_):
            queue.recover_all(self.f.factory,later)
            return self.f.evidence['findings']
        self.assertEqual(queue.run_one(self.f.factory,self.f.app.state.settings,generate=late),'discarded')
        self.assertEqual(self.event_count('refund'),1); self.assertEqual(self.event_count('charge'),0)
    def test_global_slots_bounded_and_paused_worker(self):
        self.f.post()
        with queue.provider_slot(self.f.engine) as first, queue.provider_slot(self.f.engine) as second:
            self.assertTrue(first and second); self.assertIsNone(self.work())
        paused=replace(self.f.app.state.settings,wallet_requests_paused=True)
        self.assertIsNone(queue.run_one(self.f.factory,paused)); self.assertEqual(self.event_count('charge'),0)
        self.assertEqual(self.work(),'ready')


if __name__=='__main__': unittest.main()
