import unittest,sys,uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from fastapi.testclient import TestClient
from qd766.backend.app import create_app
from qd766.backend.config import Settings
from qd766.backend.presence import PresenceTracker
from qd766.backend.auth import digest
from qd766.backend.models import Base,UserAccount,LoginSession


class PresenceTests(unittest.TestCase):
    def test_deduplicate_expire_and_bound_memory(self):
        now=[0];tracker=PresenceTracker(clock=lambda:now[0],capacity=2)
        self.assertEqual(tracker.count('a'),1);self.assertEqual(tracker.count('a'),1)
        now[0]=60;self.assertEqual(tracker.count('b'),2)
        self.assertEqual(tracker.count('c'),2)
        now[0]=240;self.assertEqual(tracker.count(),0)
        tracker.count('a');tracker.discard('a');self.assertEqual(tracker.count(),0)

    def test_public_aggregate_only_admitted_unique_accounts_and_logout(self):
        app=create_app(Settings(database_url='sqlite+pysqlite://',public_read_only=True,require_login=True,
            invite_required=True,google_client_id='test',google_client_secret='test-secret',
            google_redirect_uri='https://testserver/api/v1/auth/google/callback'))
        Base.metadata.create_all(app.state.engine)
        with app.state.session_factory.begin() as db:
            for n in (0,1):
                account=UserAccount(id=uuid.uuid4(),external_subject=str(n),display_name='Private name',trial_admitted=n==0)
                db.add(account);db.flush()
                for suffix in ('a','b'):
                    db.add(LoginSession(token_hash=digest(f'{n}{suffix}'),account_id=account.id,csrf_token='csrf',expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        client=TestClient(app)
        try:
            public=client.get('/api/v1/presence')
            self.assertEqual(public.status_code,200);self.assertEqual(public.json()['onlineUsers'],0)
            for token in ('0a','0b','1a','invalid'):
                client.cookies.set('qd766_session',token)
                result=client.get('/api/v1/presence')
                self.assertEqual(result.status_code,200);self.assertEqual(result.json()['onlineUsers'],1)
                self.assertEqual(set(result.json()),{'onlineUsers','windowSeconds','scope'})
                self.assertEqual(result.headers['cache-control'],'no-store')
            self.assertEqual(client.post('/api/v1/presence').status_code,403)
            client.cookies.set('qd766_session','0a')
            self.assertEqual(client.post('/api/v1/auth/logout',headers={'X-QD766-CSRF':'csrf'},follow_redirects=False).status_code,303)
            self.assertEqual(client.get('/api/v1/presence').json()['onlineUsers'],0)
        finally:client.close();app.state.engine.dispose()
