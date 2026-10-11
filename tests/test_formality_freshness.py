import sys,unittest,uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
from dataclasses import replace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from test_user_collection import UserCollectionTest
from qd766.backend.formality_freshness import daily_cutoff,VIETNAM
from qd766.backend.models import Snapshot,PaidDataRequest,CollectionJob,UserAccount
from qd766.backend.paid_requests import settle_paid_requests_for_job
from sqlalchemy import select,func

class FreshnessBoundaryTest(unittest.TestCase):
    def test_vietnam_midnight_and_finished_periods(self):
        now=datetime(2026,10,10,17,0,tzinfo=timezone.utc)
        for kind,value in [('month',10),('quarter',4),('year',None)]:
            self.assertEqual(daily_cutoff(kind,2026,value,now=now),now)
        for kind,value in [('month',9),('quarter',3),('year',None)]:
            self.assertIsNone(daily_cutoff(kind,2025 if kind=='year' else 2026,value,now=now))

class FreshnessFlowTest(UserCollectionTest):
    def test_old_open_period_requires_new_five_credit_job_and_history_is_pinned(self):
        self.app.state.settings=replace(self.app.state.settings,formality_credit_cost=5)
        first=self.submit();self.assertEqual(first.status_code,202,first.text);self.settle()
        cutoff=daily_cutoff('year',2026,None)
        self.assertIsNotNone(cutoff)
        with self.factory.begin() as db:
            old=db.scalar(select(Snapshot));old.created_at=cutoff-timedelta(seconds=1)
            old.province_aggregated_score=11
            old_id=str(old.id)
        params={'period_type':'year','year':2026,'scope':'formality','formality_id':str(self.formality),'root_department_id':str(self.root.root_department_id)}
        self.assertEqual(self.clients[0].get('/api/v1/me/formalities',params=params).json()['items'],[])
        quote=self.quote().json();self.assertEqual(quote['totalCredits'],5)
        self.assertEqual(self.clients[0].get('/api/v1/dashboard/selection',params=params).status_code,403)
        historical=self.clients[0].get('/api/v1/dashboard/selection',params={**params,'snapshot_id':old_id})
        self.assertEqual(historical.status_code,200,historical.text)
        self.assertEqual(self.clients[1].get('/api/v1/dashboard/selection',params={**params,'snapshot_id':old_id}).status_code,403)
        # Simulate the next day's enqueue key; preserve the completed predecessor.
        with self.factory.begin() as db:
            old_job=db.scalar(select(CollectionJob));old_job.idempotency_key+=':yesterday'
            old_request=db.scalar(select(PaidDataRequest));old_request.dataset_key+=':yesterday'
        token=str(uuid.uuid4());second=self.submit(quote=quote['quote'],token=token)
        self.assertEqual(second.status_code,202,second.text);self.assertEqual(second.json()['availableCredits'],0)
        self.assertEqual(self.submit(quote=quote['quote'],token=token).json()['availableCredits'],0)
        with self.factory.begin() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),2)
            job=db.scalar(select(CollectionJob).where(CollectionJob.state=='queued'))
            new=Snapshot(snapshot_key='new-day',schema_version=1,root_department_id=self.root.root_department_id,period_type='year',year=2026,scope='formality',formality_id=self.formality,state='complete',policy={},status_detail={},province_aggregated_score=22)
            db.add(new);db.flush();job.state='succeeded';settle_paid_requests_for_job(db,job,new)
        rows=self.clients[0].get('/api/v1/me/formality-requests').json()['items']
        self.assertEqual(len(rows),2);self.assertEqual(len({r['snapshotId'] for r in rows}),2)
        self.assertEqual(self.quote().json()['totalCredits'],0)
        self.assertEqual(len(self.clients[0].get('/api/v1/me/formalities',params=params).json()['items']),1)
        old_response=self.clients[0].get('/api/v1/dashboard/selection',params={**params,'snapshot_id':old_id})
        self.assertEqual(old_response.status_code,200,old_response.text)
        self.assertEqual(old_response.json()['snapshot']['provinceAggregatedScore'],11)

    def test_closed_period_keeps_old_entitlement_free(self):
        self.selection['year']=2025
        first=self.submit();self.assertEqual(first.status_code,202)
        with self.factory.begin() as db:
            snapshot=Snapshot(snapshot_key='closed',schema_version=1,root_department_id=self.root.root_department_id,period_type='year',year=2025,scope='formality',formality_id=self.formality,state='complete',policy={},status_detail={},created_at=datetime(2025,1,1,tzinfo=timezone.utc))
            db.add(snapshot);db.flush();settle_paid_requests_for_job(db,db.scalar(select(CollectionJob)),snapshot)
        self.assertEqual(self.quote().json()['totalCredits'],0)
        self.assertEqual(len(self.clients[0].get('/api/v1/me/formalities?period_type=year&year=2025').json()['items']),1)
