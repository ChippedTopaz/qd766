"""Anonymous aggregate only. Ephemeral presence for this single backend instance."""
from collections import OrderedDict
from threading import Lock
import time
from fastapi import APIRouter, Request, Response
from .auth import current_session, SESSION_COOKIE


class PresenceTracker:
    def __init__(self, *, clock=time.monotonic, window=180, capacity=10000):
        self.clock=clock;self.window=window;self.capacity=capacity
        self.seen=OrderedDict();self.lock=Lock()

    def count(self, account_id=None):
        with self.lock:
            now=self.clock()
            while self.seen and next(iter(self.seen.values()))<=now-self.window:
                self.seen.popitem(last=False)
            if account_id is not None:
                self.seen.pop(account_id,None);self.seen[account_id]=now
                while len(self.seen)>self.capacity:self.seen.popitem(last=False)
            return len(self.seen)

    def discard(self, account_id):
        with self.lock:self.seen.pop(account_id,None)


router=APIRouter()


@router.get('/api/v1/presence', tags=['health'])
def online_users(request:Request,response:Response):
    account_id=None
    token=request.cookies.get(SESSION_COOKIE)
    if token:
        with request.app.state.session_factory() as db:
            _,account=current_session(db,token)
            if account and account.trial_admitted:account_id=account.id
    response.headers['Cache-Control']='no-store'
    return {'onlineUsers':request.app.state.presence.count(account_id),
            'windowSeconds':180,'scope':'backend-instance'}
