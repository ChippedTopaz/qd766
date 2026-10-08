import sys,unittest,uuid,copy,tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone,date
from types import SimpleNamespace
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from qd766.backend.models import Base,DailyObservation
from qd766.backend.daily_history import daily_target,history_payload,validate_daily_snapshot
from qd766.backend.province_refresh import VIETNAM,daily_fresh_after
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.national_summaries import store_national_summary
from qd766.backend.dashboard import NATIONAL_GROUP_CODES
from qd766.national_summary import NationalSummaryCapture
from qd766.periods import PeriodSelection
from test_backend import snapshot_payload,ROOT_ID,CHILD_ID

class DailyHistoryTest(unittest.TestCase):
    def test_different_source_agencies_retained_without_fabricated_scores(self):
        stamp=datetime(2026,10,7,4,10,tzinfo=VIETNAM);root=uuid.uuid4();one=uuid.uuid4();two=uuid.uuid4()
        datasets=[SimpleNamespace(group_name=group,entities=[SimpleNamespace(entity_kind='root',api_score=1),
            SimpleNamespace(entity_kind='child',department_id=one)]+([SimpleNamespace(entity_kind='child',department_id=two)] if index==0 else []))
            for index,group in enumerate(NATIONAL_GROUP_CODES)]
        snapshot=SimpleNamespace(state='complete',scope='all',root_department_id=root,period_type='year',year=2026,period_value=None,created_at=stamp,datasets=datasets)
        summary=SimpleNamespace(period_type='year',year=2026,period_value=None,captured_at=stamp,group_count=6,province_count=34,completeness_state='complete')
        coverage=validate_daily_snapshot(snapshot,summary,date(2026,10,6),stamp-timedelta(minutes=10),PeriodSelection('year',2026,None),root)
        self.assertEqual(coverage['completeUnits'],1);self.assertEqual(coverage['sourceUnits'],2)
        self.assertEqual(len(coverage['missingByGroup']),5)
        self.assertEqual(len(datasets[0].entities),3);self.assertEqual(len(datasets[1].entities),2)
        with self.assertRaises(ValueError):validate_daily_snapshot(snapshot,summary,date(2026,10,6),stamp+timedelta(minutes=1),PeriodSelection('year',2026,None),root)

    def test_reporting_day_and_rollovers(self):
        day,boundary,periods=daily_target(datetime(2026,10,6,5,tzinfo=VIETNAM))
        self.assertEqual(day,date(2026,10,5));self.assertEqual(boundary.hour,5)
        self.assertEqual(daily_target(datetime(2026,10,6,4,59,tzinfo=VIETNAM))[0],date(2026,10,4))
        self.assertEqual(daily_target(datetime(2026,10,5,22,tzinfo=timezone.utc))[0],day)
        closing=daily_target(datetime(2027,1,1,5,tzinfo=VIETNAM))[2]
        self.assertEqual({(p.type,p.year,p.value) for p in closing},{('month',2026,12),('quarter',2026,4),('year',2026,None)})
        self.assertEqual(daily_target(datetime(2027,1,2,5,tzinfo=VIETNAM))[2][0].year,2027)
        self.assertEqual(daily_target(datetime(2028,3,1,5,tzinfo=VIETNAM))[0],date(2028,2,29))

    def test_freshness_waits_for_daily_completion(self):
        self.assertEqual(daily_fresh_after(datetime(2026,10,6,5,59,tzinfo=VIETNAM)).day,5)
        self.assertEqual(daily_fresh_after(datetime(2026,10,6,6,tzinfo=VIETNAM)).day,6)

    def test_real_daily_versions_and_same_content_resume(self):
        engine=create_engine('sqlite://');Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                stamp=datetime(2026,10,6,2,10,tzinfo=VIETNAM)
                capture=NationalSummaryCapture(PeriodSelection('month',2026,8),{}, {'evaluation':[
                    {'departmentId':ROOT_ID,'totalScore':61,'groupScores':{code:1 for code in NATIONAL_GROUP_CODES.values()}}]},'a'*64,stamp)
                one,_=store_national_summary(db,capture,observation_id='day-1')
                resumed,created=store_national_summary(db,capture,observation_id='day-1')
                self.assertEqual(one.id,resumed.id);self.assertFalse(created)
                later=copy.deepcopy(capture)
                object.__setattr__(later,'captured_at',stamp+timedelta(days=1))
                two,_=store_national_summary(db,later,observation_id='day-2')
                self.assertNotEqual(one.id,two.id);self.assertEqual(one.captured_at,stamp)
                for index,summary in enumerate([one,two]):
                    payload=snapshot_payload();dataset=payload['datasets'][0]
                    payload['datasets']=[dict(copy.deepcopy(dataset),group=group) for group in NATIONAL_GROUP_CODES]
                    payload['status'].update(requiredGroups=list(NATIONAL_GROUP_CODES),loadedGroups=list(NATIONAL_GROUP_CODES))
                    snapshot=store_normalized_snapshot(db,payload,observation_id='day-'+str(index+1))
                    snapshot.created_at=stamp+timedelta(days=index)
                    db.add(DailyObservation(block_key='test-'+str(index),report_date=date(2026,10,5)+timedelta(days=index),
                        root_department_id=uuid.UUID(ROOT_ID),period_type='month',year=2026,period_value=8,
                        snapshot_id=snapshot.id,national_summary_id=summary.id,captured_at=snapshot.created_at))
                db.commit()
                history=history_payload(db,uuid.UUID(ROOT_ID),uuid.UUID(CHILD_ID),PeriodSelection('month',2026,8))
                self.assertEqual(len(history['days']),1);self.assertEqual(len(history['days'][0]['groups']),6)
                self.assertEqual(history['days'][0]['reportDate'],'2026-10-06')
                self.assertEqual(history['reportingPolicy'],'previous-day-05:00-Asia/Ho_Chi_Minh')
                self.assertEqual(len(list(db.scalars(select(DailyObservation)))),2)
                self.assertEqual(history['days'][0]['rank'],1)
                snapshot.created_at=stamp-timedelta(days=1)
                with self.assertRaises(ValueError):validate_daily_snapshot(snapshot,one,date(2026,10,5),stamp-timedelta(minutes=10),PeriodSelection('month',2026,8),uuid.UUID(ROOT_ID))
        finally:engine.dispose()

if __name__=='__main__':unittest.main()
