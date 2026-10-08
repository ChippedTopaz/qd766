import sys, unittest, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from qd766.backend import create_app
from qd766.backend.config import Settings
from qd766.backend.auth import digest
from qd766.backend.models import Base, UserAccount, LoginSession, TriviaQuestion, TriviaAnswer, TriviaProfile


class TriviaTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(Settings(database_url='sqlite+pysqlite://',public_read_only=True,require_login=True,invite_required=True,
            google_client_id='test',google_client_secret='secret',google_redirect_uri='https://testserver/api/v1/auth/google/callback'))
        Base.metadata.create_all(self.app.state.engine)
        self.client=TestClient(self.app,base_url='https://testserver')
        self.ids={}
        with self.app.state.session_factory.begin() as db:
            for token,role,admitted in [('owner','admin',True),('agency','user',True),('pending','user',False),('locked','user',True)]:
                a=UserAccount(external_subject=token,display_name=token,role=role,trial_admitted=admitted,credit_balance=123,active=token!='locked')
                db.add(a);db.flush();self.ids[token]=a.id
                db.add(LoginSession(token_hash=digest(token),account_id=a.id,csrf_token='csrf',expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        self.headers={'X-QD766-CSRF':'csrf'}
        self.login('owner')

    def tearDown(self):
        self.client.close();self.app.state.engine.dispose()

    def login(self,token):
        self.client.cookies.clear()
        if token:self.client.cookies.set('qd766_session',token)

    def create(self,**extra):
        self.login('owner')
        payload=dict(prompt='Hồ sơ quá hạn ảnh hưởng nhóm nào?',choices=['Tiến độ và hài lòng','Không nhóm nào'],correctIndex=0,explanation='Quá hạn ảnh hưởng cả hai nhóm.',state='published')
        payload.update(extra)
        response=self.client.post('/api/v1/admin/trivia',json=payload,headers=self.headers)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def current(self):
        r=self.client.get('/api/v1/me/trivia');self.assertEqual(r.status_code,200,r.text);return r.json()

    def answer(self,q,choice=0,headers=None):
        return self.client.post('/api/v1/me/trivia/answer',json={'questionId':q['id'],'roundId':q.get('roundId',str(self.round_id())),'choice':choice},headers=self.headers if headers is None else headers)

    def round_id(self):
        with self.app.state.session_factory() as db:
            token=self.client.cookies.get('qd766_session')
            profile=db.get(TriviaProfile,self.ids[token]);return profile.round_id if profile else uuid.uuid4()

    def test_pending_persists_and_answer_is_hidden(self):
        q=self.create();self.login('agency')
        a=self.current();b=self.current()
        self.assertEqual(a['question'],b['question']);self.assertEqual(a['question']['id'],q['id'])
        self.assertEqual(set(a['question']),{'id','prompt','choices','roundId','expiresAt'})
        self.assertEqual(a['stats']['score'],0)

    def test_leaderboard_top20_lifetime_totals_privacy_and_auth(self):
        from qd766.backend.models import Department
        q=self.create()
        province=uuid.uuid4()
        with self.app.state.session_factory.begin() as db:
            db.add(Department(id=province,name='UBND tỉnh thử nghiệm'))
            db.flush()
            for index in range(25):
                account=UserAccount(external_subject=f'ranked-{index}',display_name=f'Người chơi {index:02}',
                    email=f'private-{index}@example.invalid',trial_admitted=True,root_department_id=province)
                db.add(account);db.flush()
                db.add(TriviaProfile(account_id=account.id,best=25-index,score=0))
                for attempt in range(2):
                    db.add(TriviaAnswer(account_id=account.id,question_id=uuid.UUID(q['id']),round_id=uuid.uuid4(),
                        correct=True,timed_out=False,score_after=1,streak_after=1,best_after=25-index,answered_after=1))
            db.add(TriviaProfile(account_id=self.ids['locked'],best=100))
            db.add(TriviaProfile(account_id=self.ids['pending'],best=99))
        self.login('agency')
        response=self.client.get('/api/v1/me/trivia/leaderboard')
        self.assertEqual(response.status_code,200,response.text)
        players=response.json()['players'];self.assertEqual(len(players),20)
        self.assertEqual(players[0],{'rank':1,'name':'Người chơi 00','province':'UBND tỉnh thử nghiệm','best':25,'correctAnswers':2})
        self.assertEqual(players[-1]['best'],6)
        self.assertNotIn('email',response.text);self.assertNotIn('external_subject',response.text)
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertEqual(self.client.post('/api/v1/me/trivia/leaderboard').status_code,405)
        for token in (None,'pending','locked'):
            self.login(token)
            self.assertIn(self.client.get('/api/v1/me/trivia/leaderboard').status_code,(401,403))

    def test_scoring_streak_wrong_and_idempotency_never_change_credit(self):
        first=self.create();second=self.create(prompt='Câu hỏi thứ hai cần được trả lời?');third=self.create(prompt='Câu hỏi thứ ba cần được trả lời?')
        self.login('agency')
        # The database order is stable; do not assume UUID order within one timestamp.
        q=self.current()['question'];first_answered=q;r=self.answer(q).json()
        self.assertEqual(r['stats'],dict(score=1,streak=1,best=1,answered=1))
        replay=self.answer(q,1).json();self.assertEqual(replay,r)
        q=self.current()['question'];self.assertEqual(self.answer(q).json()['stats']['streak'],2)
        q=self.current()['question'];r=self.answer(q,1).json()
        self.assertEqual(r['stats'],dict(score=2,streak=0,best=2,answered=3))
        self.assertEqual(self.answer(first_answered).json()['stats'],r['stats'])
        self.assertIsNone(self.current()['question'])
        with self.app.state.session_factory() as db:
            self.assertEqual(db.get(UserAccount,self.ids['agency']).credit_balance,123)
            self.assertEqual(db.scalar(select(func.count()).select_from(TriviaAnswer)),3)

    def test_only_assigned_question_can_be_answered(self):
        a=self.create();b=self.create(prompt='Một câu hỏi thứ hai trong ngân hàng?');self.login('agency')
        pending=self.current()['question'];other=b if pending['id']==a['id'] else a
        self.assertEqual(self.answer(other).status_code,409)
        self.assertEqual(self.answer(pending,4).status_code,422)
        self.assertEqual(self.current()['stats']['answered'],0)

    def test_auth_csrf_admin_and_account_isolation(self):
        q=self.create();self.login('agency');self.current()
        self.assertEqual(self.answer(q,headers={}).status_code,403)
        self.assertEqual(self.client.get('/api/v1/admin/trivia').status_code,403)
        self.assertEqual(self.client.post('/api/v1/admin/trivia',json=q,headers=self.headers).status_code,403)
        self.answer(q);self.login('owner');self.assertEqual(self.current()['stats']['score'],0)
        for token in (None,'pending','locked'):
            self.login(token);self.assertIn(self.client.get('/api/v1/me/trivia').status_code,(401,403))

    def test_draft_publish_lock_revision_and_withdraw(self):
        q=self.create(state='draft');self.login('agency');self.assertIsNone(self.current()['question'])
        self.login('owner')
        payload={k:q[k] for k in ('prompt','choices','correctIndex','explanation','state','revision')};payload['state']='published'
        url='/api/v1/admin/trivia/'+q['id']
        published=self.client.post(url,json=payload,headers=self.headers)
        self.assertEqual(published.status_code,200,published.text);q=published.json();self.assertTrue(q['locked'])
        self.assertEqual(self.client.post(url,json=payload,headers=self.headers).status_code,409)
        payload['revision']=q['revision'];payload['prompt']='Nội dung đã bị chỉnh sửa?'
        self.assertEqual(self.client.post(url,json=payload,headers=self.headers).status_code,409)
        self.login('agency');self.current();self.login('owner')
        payload['prompt']=q['prompt'];payload['state']='retired'
        self.assertEqual(self.client.post(url,json=payload,headers=self.headers).status_code,200)
        self.login('agency');self.assertEqual(self.answer(q).status_code,409);self.assertIsNone(self.current()['question'])

    def test_bank_ten_per_page_and_state_filter_with_search(self):
        for i in range(12):self.create(prompt=f'Câu hỏi phân trang kiểm tra số {i}?',state='draft')
        self.create(prompt='Câu hỏi đã công khai?')
        self.create(prompt='Câu hỏi đã thu hồi?',state='retired')
        first=self.client.get('/api/v1/admin/trivia?state=draft').json()
        self.assertEqual(first['total'],12);self.assertEqual(len(first['questions']),10)
        second=self.client.get('/api/v1/admin/trivia?state=draft&offset=10&limit=10').json()
        self.assertEqual(len(second['questions']),2)
        self.assertTrue(set(q['id'] for q in first['questions']).isdisjoint(q['id'] for q in second['questions']))
        for state in ('published','retired'):
            result=self.client.get('/api/v1/admin/trivia?state='+state).json()
            self.assertEqual(result['total'],1);self.assertEqual(result['questions'][0]['state'],state)
        self.assertEqual(self.client.get('/api/v1/admin/trivia?state=draft&q=thu%20h%E1%BB%93i').json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/admin/trivia?state=invalid').status_code,422)

    def test_quick_publish_requires_admin_csrf_revision_and_draft(self):
        q=self.create(state='draft');url=f"/api/v1/admin/trivia/{q['id']}/publish"
        payload={'revision':q['revision']}
        self.assertEqual(self.client.post(url,json=payload).status_code,403)
        self.login('agency');self.assertEqual(self.client.post(url,json=payload,headers=self.headers).status_code,403)
        self.login('owner')
        self.assertEqual(self.client.post(url,json={'revision':q['revision']+1},headers=self.headers).status_code,409)
        response=self.client.post(url,json=payload,headers=self.headers);self.assertEqual(response.status_code,200,response.text)
        published=response.json();self.assertEqual(published['state'],'published');self.assertTrue(published['locked'])
        self.assertEqual(published['choices'],q['choices']);self.assertEqual(published['revision'],q['revision']+1)
        self.assertEqual(self.client.post(url,json=payload,headers=self.headers).status_code,409)
        self.assertEqual(self.client.post(url,json={'revision':published['revision']},headers=self.headers).status_code,409)
        self.login('agency');self.assertEqual(self.current()['question']['id'],q['id'])
        with self.app.state.session_factory() as db:self.assertEqual(db.get(UserAccount,self.ids['agency']).credit_balance,123)

    def test_max_three_new_choices_preserves_locked_legacy(self):
        payload=dict(prompt='Câu hỏi có bốn đáp án?',choices=['Một','Hai','Ba','Bốn'],correctIndex=3,state='draft')
        self.assertEqual(self.client.post('/api/v1/admin/trivia',json=payload,headers=self.headers).status_code,422)
        q=self.create()
        with self.app.state.session_factory.begin() as db:
            legacy=db.get(TriviaQuestion,uuid.UUID(q['id']));legacy.choices=payload['choices'];legacy.correct_index=3
        legacy=self.client.get('/api/v1/admin/trivia').json()['questions'][0]
        old={k:legacy[k] for k in ('prompt','choices','correctIndex','explanation','revision')};old['state']='retired'
        changed=self.client.post('/api/v1/admin/trivia/'+q['id'],json=old,headers=self.headers)
        self.assertEqual(changed.status_code,200,changed.text);self.assertEqual(changed.json()['choices'],payload['choices'])
        with self.app.state.session_factory.begin() as db:
            draft=db.get(TriviaQuestion,uuid.UUID(q['id']));draft.state='draft';draft.locked=False
        self.assertEqual(self.client.post(f"/api/v1/admin/trivia/{q['id']}/publish",json={'revision':changed.json()['revision']},headers=self.headers).status_code,422)

    def test_bad_questions_and_wrong_methods(self):
        self.login('owner')
        payload=dict(prompt='Câu hỏi kiểm tra?',choices=['Trùng','Trùng'],correctIndex=0)
        self.assertEqual(self.client.post('/api/v1/admin/trivia',json=payload,headers=self.headers).status_code,422)
        payload['choices']=['Một','Hai'];payload['correctIndex']=3
        self.assertEqual(self.client.post('/api/v1/admin/trivia',json=payload,headers=self.headers).status_code,422)
        self.assertEqual(self.client.post('/api/v1/me/trivia').status_code,405)

    def test_timeout_resets_streak_and_moves_once_to_next_random_question(self):
        from unittest.mock import patch
        for i in range(3):self.create(prompt=f'Câu hỏi ngẫu nhiên số {i} trong ngân hàng?')
        self.login('agency')
        with patch('qd766.backend.trivia.secrets.choice',side_effect=lambda ids:ids[-1]) as random_choice:
            first=self.current()['question'];self.answer(first)
            second=self.current()['question']
            self.assertNotEqual(first['id'],second['id'])
            with self.app.state.session_factory.begin() as db:
                db.get(TriviaProfile,self.ids['agency']).pending_deadline=datetime.now(timezone.utc)-timedelta(seconds=1)
            body=self.current()
            self.assertTrue(body['timedOut']);self.assertEqual(body['stats'],dict(score=1,streak=0,best=1,answered=2))
            self.assertNotIn(body['question']['id'],(first['id'],second['id']))
            self.assertEqual(self.current()['question'],body['question'])
            self.assertTrue(self.answer(second).json()['timedOut'])
            self.assertEqual(self.current()['stats']['answered'],2)
            self.assertEqual(random_choice.call_count,3)

    def test_late_correct_answer_scores_zero_and_round_restart_is_safe(self):
        self.create();self.login('agency');body=self.current();q=body['question']
        endpoint='/api/v1/me/trivia/restart';payload={'roundId':body['roundId']}
        self.assertEqual(self.client.post(endpoint,json=payload,headers=self.headers).status_code,409)
        with self.app.state.session_factory.begin() as db:
            db.get(TriviaProfile,self.ids['agency']).pending_deadline=datetime.now(timezone.utc)-timedelta(seconds=1)
        answer=self.answer(q).json();self.assertTrue(answer['timedOut']);self.assertFalse(answer['correct'])
        self.assertEqual(answer['stats']['score'],0);self.assertIsNone(self.current()['question'])
        self.assertEqual(self.client.post(endpoint,json=payload).status_code,403)
        restarted=self.client.post(endpoint,json=payload,headers=self.headers).json()
        self.assertNotEqual(restarted['roundId'],body['roundId']);self.assertEqual(restarted['question']['id'],q['id'])
        self.assertEqual(restarted['stats']['answered'],0)
        self.assertEqual(self.answer(q).status_code,409,'old-tab submission cannot score the new round')
        self.assertEqual(self.answer(restarted['question']).json()['stats']['score'],1)
        replay=self.client.post(endpoint,json=payload,headers=self.headers).json()
        self.assertEqual(replay['stats']['score'],1,'duplicate restart cannot reset a new round')
        self.assertEqual(replay['stats']['best'],1)

    def test_independent_random_assignment_and_deadline_survive_new_session(self):
        from unittest.mock import patch
        for i in range(2):self.create(prompt=f'Câu hỏi số {i} phục vụ chọn ngẫu nhiên?')
        self.login('agency')
        with patch('qd766.backend.trivia.secrets.choice',side_effect=lambda ids:ids[0]):a=self.current()['question']
        self.login('owner')
        with patch('qd766.backend.trivia.secrets.choice',side_effect=lambda ids:ids[-1]):b=self.current()['question']
        self.assertNotEqual(a['id'],b['id'])
        self.login('agency');self.assertEqual(self.current()['question'],a)

    def test_deadline_is_timezone_safe(self):
        from qd766.backend.trivia import expired
        now=datetime.now(timezone.utc)
        profile=TriviaProfile(pending_deadline=(now-timedelta(seconds=1)).astimezone(timezone(timedelta(hours=7))))
        self.assertTrue(expired(profile,now))

    def test_admin_counts_rounds_deduplicates_people_and_searches_all_questions(self):
        q=self.create(prompt='Câu hỏi kiểm tra thống kê số lượt đúng?')
        self.login('agency');body=self.current();self.answer(body['question'])
        restarted=self.client.post('/api/v1/me/trivia/restart',json={'roundId':body['roundId']},headers=self.headers).json()
        self.answer(restarted['question']);self.answer(restarted['question'])
        self.login('owner');self.answer(self.current()['question'],1)
        row=self.client.get('/api/v1/admin/trivia',params={'q':'THỐNG KÊ'}).json()['questions'][0]
        self.assertEqual(row['correctAttempts'],2);self.assertEqual(row['correctUsers'],1)
        users=self.client.get(f"/api/v1/admin/trivia/{q['id']}/correct-users").json()
        self.assertEqual(users['total'],1);self.assertEqual(users['users'][0]['name'],'agency')
        self.assertEqual(users['users'][0]['correctAttempts'],2)
        self.assertEqual(self.client.get('/api/v1/admin/trivia',params={'q':'%'}).json()['total'],0)
        self.create(prompt='Câu hỏi thứ hai phục vụ kiểm tra phân trang?')
        a=self.client.get('/api/v1/admin/trivia?limit=1').json();b=self.client.get('/api/v1/admin/trivia?limit=1&offset=1').json()
        self.assertEqual(a['total'],2);self.assertNotEqual(a['questions'][0]['id'],b['questions'][0]['id'])
        self.login('agency');self.assertEqual(self.client.get(f"/api/v1/admin/trivia/{q['id']}/correct-users").status_code,403)
        self.login(None);self.assertEqual(self.client.get(f"/api/v1/admin/trivia/{q['id']}/correct-users").status_code,401)

    def test_missing_schema_does_not_break_existing_site(self):
        TriviaAnswer.__table__.drop(self.app.state.engine)
        self.assertFalse(self.current()['available'])
        self.assertFalse(self.client.get('/api/v1/admin/trivia').json()['available'])

    def test_additive_migration_matches_models_without_touching_accounts(self):
        import importlib.util
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from sqlalchemy import inspect
        path=Path(__file__).resolve().parents[1]/'alembic/versions/20261007_0023_trivia.py'
        spec=importlib.util.spec_from_file_location('trivia_migration',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for model in (TriviaAnswer,TriviaProfile,TriviaQuestion):model.__table__.drop(self.app.state.engine)
        with self.app.state.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                module.upgrade()
        for model in (TriviaQuestion,TriviaProfile,TriviaAnswer):
            self.assertEqual(set(model.__table__.columns.keys()),{c['name'] for c in inspect(self.app.state.engine).get_columns(model.__tablename__)})
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(UserAccount)),4)
        q=self.create();self.login('agency');self.current();self.assertEqual(self.answer(q).status_code,200)


if __name__=='__main__':unittest.main()
