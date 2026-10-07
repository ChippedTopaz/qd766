import unittest,uuid
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
from sqlalchemy import select,func
import test_trivia
from qd766.backend.models import TriviaQuestion,TriviaAnswer,TriviaProfile,UserAccount

class DeleteTests(unittest.TestCase):
    def setUp(self):
        self.f=test_trivia.TriviaTests();self.f.setUp();self.client=self.f.client
        self.questions=[self.f.create(prompt=f'Câu hỏi kiểm thử xóa thứ {n}?') for n in range(7)]
    def tearDown(self):self.f.tearDown()
    def history(self,rounds,current=-1,pending=None):
        account=self.f.ids['agency'];roundids=[uuid.uuid4() for _ in rounds];best=0;stamp=datetime(2026,10,7,tzinfo=timezone.utc)
        with self.f.app.state.session_factory.begin() as db:
            for r,answers in enumerate(rounds):
                score=streak=0
                for n,(q,correct) in enumerate(answers,1):
                    score+=int(correct);streak=streak+1 if correct else 0;best=max(best,streak)
                    db.add(TriviaAnswer(account_id=account,question_id=uuid.UUID(self.questions[q]['id']),round_id=roundids[r],choice=0 if correct else 1,correct=correct,timed_out=False,score_after=score,streak_after=streak,best_after=best,answered_after=n,created_at=stamp+timedelta(seconds=r*20+n)))
                if r==current%len(rounds):currentstats=(score,streak,len(answers))
            db.add(TriviaProfile(account_id=account,round_id=roundids[current],score=currentstats[0],streak=currentstats[1],answered=currentstats[2],best=best,pending_id=uuid.UUID(self.questions[pending]['id']) if pending is not None else None,pending_deadline=stamp+timedelta(days=1) if pending is not None else None))
        return roundids
    def delete(self,n=0,body=None,headers=None):
        return self.client.post('/api/v1/admin/trivia/'+self.questions[n]['id']+'/delete',json=body or {'revision':1,'confirm':True},headers=self.f.headers if headers is None else headers)
    def stats(self):
        with self.f.app.state.session_factory() as db:
            p=db.get(TriviaProfile,self.f.ids['agency']);return(p.score,p.streak,p.best,p.answered)
    def test_correct_removed_every_round_recount_best_and_snapshots(self):
        ids=self.history([[(1,True),(0,True),(2,True)],[(0,True),(3,True)]])
        result=self.delete();self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['deletedAnswers'],2)
        self.assertEqual(self.stats(),(1,1,2,1))
        with self.f.app.state.session_factory() as db:
            self.assertIsNone(db.get(TriviaQuestion,uuid.UUID(self.questions[0]['id'])))
            self.assertEqual(db.scalar(select(func.count()).select_from(TriviaAnswer).where(TriviaAnswer.question_id==uuid.UUID(self.questions[0]['id']))),0)
            rows=list(db.scalars(select(TriviaAnswer).where(TriviaAnswer.round_id==ids[0]).order_by(TriviaAnswer.answered_after)))
            self.assertEqual([(a.score_after,a.streak_after,a.answered_after) for a in rows],[(1,1,1),(2,2,2)])
            self.assertTrue(all(a.best_after<=2 for a in db.scalars(select(TriviaAnswer))))
            self.assertTrue(all(a.credit_balance==123 for a in db.scalars(select(UserAccount))))
        self.assertEqual(self.delete().status_code,404)
        self.assertEqual(self.client.get('/api/v1/admin/trivia/'+self.questions[0]['id']+'/correct-users').status_code,404)
    def test_other_round_best_is_kept(self):
        self.history([[(1,True),(2,True),(3,True),(4,True)],[(0,True),(5,True)]])
        self.delete();self.assertEqual(self.stats(),(1,1,4,1))
    def test_deleting_wrong_does_not_join_broken_streaks(self):
        self.history([[(1,True),(2,True),(0,False),(3,True),(4,True)]])
        self.delete();self.assertEqual(self.stats(),(4,2,2,4))
        self.delete(2);self.assertEqual(self.stats(),(3,2,2,3))
    def test_deleting_last_wrong_does_not_revive_streak(self):
        self.history([[(1,True),(2,True),(0,False)]])
        self.delete();self.assertEqual(self.stats(),(2,0,2,2))
    def test_pending_and_stale_answer(self):
        self.history([[(1,True)]],pending=0);self.delete()
        with self.f.app.state.session_factory() as db:
            p=db.get(TriviaProfile,self.f.ids['agency']);self.assertIsNone(p.pending_id);self.assertIsNone(p.pending_deadline)
        self.f.login('agency');self.assertEqual(self.f.answer(self.questions[0]).status_code,409)
        self.assertNotEqual(self.f.current()['question']['id'],self.questions[0]['id'])
    def test_admin_csrf_revision_confirmation_and_rollback(self):
        self.history([[(0,True)]])
        self.assertEqual(self.delete(headers={}).status_code,403)
        for body in ({'revision':2,'confirm':True},{'revision':1,'confirm':False},{'revision':1,'confirm':1},{'revision':1}):
            self.assertIn(self.delete(body=body).status_code,(409,422))
        for token in ('agency','pending','locked',None):
            self.f.login(token);self.assertIn(self.delete().status_code,(401,403))
        self.f.login('owner')
        with patch('qd766.backend.trivia.audit',side_effect=RuntimeError('rollback')):
            with self.assertRaises(RuntimeError):self.delete()
        self.assertEqual(self.stats(),(1,1,1,1))
        with self.f.app.state.session_factory() as db:self.assertIsNotNone(db.get(TriviaQuestion,uuid.UUID(self.questions[0]['id'])))
    def test_only_answer_deleted_all_stats_zero_and_unaffected_account(self):
        self.history([[(0,True)]])
        with self.f.app.state.session_factory.begin() as db:db.add(TriviaProfile(account_id=self.f.ids['owner'],score=8,streak=2,best=5,answered=10))
        self.delete();self.assertEqual(self.stats(),(0,0,0,0))
        with self.f.app.state.session_factory() as db:
            p=db.get(TriviaProfile,self.f.ids['owner']);self.assertEqual((p.score,p.streak,p.best,p.answered),(8,2,5,10))

if __name__=='__main__':unittest.main()
