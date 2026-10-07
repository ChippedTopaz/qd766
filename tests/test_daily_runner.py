"""End-to-end runner on isolated SQLite, with every HTTP/source call mocked."""
import sys,unittest,tempfile,uuid,copy,io
from pathlib import Path
from datetime import datetime,timezone
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import redirect_stdout, nullcontext
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import run_daily_collection as runner
from qd766.backend.models import Base,DailyObservation,CollectionControl,Dataset
from qd766.backend.dashboard import NATIONAL_GROUP_CODES
from qd766.backend.database import create_session_factory
from qd766.national_summary import NationalSummaryCapture
from test_backend import snapshot_payload

class DailyRunnerTest(unittest.TestCase):
    def test_block_retries_transient_failure_and_reuses_capture_directory(self):
        retries=[];delays=[]
        directory=Path('retained-captures')
        with patch.object(runner,'collect_concurrent_snapshot',side_effect=[TimeoutError('temporary'),{'captures':[]}]) as collect:
            result=runner.collect_detail_block('plan','period',directory,'transport',retries.append,sleeper=delays.append)
        self.assertEqual(result,{'captures':[]})
        self.assertEqual(retries,[1]);self.assertEqual(delays,[1])
        self.assertEqual(collect.call_count,2)
        self.assertTrue(all(call.kwargs['output_dir']==directory for call in collect.call_args_list))

    def test_block_retry_is_bounded(self):
        retries=[];delays=[]
        with patch.object(runner,'collect_concurrent_snapshot',side_effect=TimeoutError('temporary')) as collect:
            with self.assertRaises(TimeoutError):
                runner.collect_detail_block(None,None,Path('captures'),None,retries.append,sleeper=delays.append)
        self.assertEqual(collect.call_count,3)
        self.assertEqual(retries,[1,2]);self.assertEqual(delays,[1,2])

    def test_safety_stop_and_invalid_data_are_not_blindly_retried(self):
        for error in (runner.SafetyStop('paused'),ValueError('invalid source')):
            with self.subTest(error=type(error).__name__),patch.object(runner,'collect_concurrent_snapshot',side_effect=error) as collect:
                with self.assertRaises(type(error)):
                    runner.collect_detail_block(None,None,Path('captures'),None,lambda _:self.fail('Must not retry'))
                self.assertEqual(collect.call_count,1)

    def test_report_date_guard_cannot_relabel_or_start_collection(self):
        with patch.object(sys,'argv',['runner','--execute','--expected-report-date','2000-01-01']),\
             patch.object(runner,'create_database_engine') as database,patch.object(runner,'load_province_roots') as roots:
            with self.assertRaisesRegex(SystemExit,'REPORT_DATE_GUARD_FAILED_NO_COLLECTION'):runner.main()
            database.assert_not_called();roots.assert_not_called()

    def test_all_102_blocks_resume_without_recapture(self):
        test_root=Path(__file__).resolve().parents[1]/'.tmp-release-preflight'
        test_root.mkdir(exist_ok=True)
        directory=test_root/('daily-test-'+uuid.uuid4().hex)
        directory.mkdir()
        with nullcontext(str(directory)) as directory:
            root=Path(directory);engine=create_engine('sqlite:///'+str(root/'test.db'));Base.metadata.create_all(engine)
            roots=[SimpleNamespace(root_department_id=uuid.UUID(int=100+i),province_name='Tỉnh '+str(i)) for i in range(34)]
            with Session(engine) as db:db.add(CollectionControl(key='dvcqg',circuit_state='closed'));db.commit()
            captures={};first_failure=[3]
            def national(period,transport):
                return NationalSummaryCapture(period,{}, {'evaluation':[{'departmentId':str(r.root_department_id),
                    'totalScore':30,'groupScores':{code:5 for code in NATIONAL_GROUP_CODES.values()}} for r in roots]},'a'*64,datetime.now(timezone.utc))
            def collect(plan,*,period,output_dir,**kwargs):
                if first_failure[0]:
                    first_failure[0]-=1
                    raise TimeoutError('Simulated isolated source failure')
                root_id=uuid.UUID(output_dir.name)
                payload=snapshot_payload(root_id=str(root_id),child_id=str(uuid.UUID(int=root_id.int+1000)))
                key={'type':period.type,'year':period.year}
                if period.type != 'year':key[period.type]=period.value
                payload['period']=key
                dataset=payload['datasets'][0]
                payload['datasets']=[dict(copy.deepcopy(dataset),group=group,period=key) for group in NATIONAL_GROUP_CODES]
                payload['status'].update(requiredGroups=list(NATIONAL_GROUP_CODES),loadedGroups=list(NATIONAL_GROUP_CODES))
                captures[output_dir]=payload
                return {'captures':[{'capturedAt':datetime.now(timezone.utc).isoformat()} for _ in NATIONAL_GROUP_CODES]}
            with patch.object(runner,'ROOT',root),patch.object(runner,'load_province_roots',return_value={str(i):r for i,r in enumerate(roots)}),\
                 patch.object(runner,'load_environment_file'),patch.object(runner,'create_database_engine',return_value=engine),\
                 patch.object(runner,'PooledHttpTransport',return_value=SimpleNamespace(close=lambda:None)),\
                 patch.object(runner,'collect_national_summary',side_effect=national) as national_mock,\
                 patch.object(runner,'collect_concurrent_snapshot',side_effect=collect) as details_mock,\
                 patch.object(runner,'build_collected_snapshot',side_effect=lambda path:SimpleNamespace(to_dict=lambda:captures[path])),\
                 patch.object(runner.time,'sleep'),patch.object(sys,'argv',['runner','--execute']),redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(),2)
                self.assertEqual(national_mock.call_count,3);self.assertEqual(details_mock.call_count,104)
                self.assertEqual(runner.main(),0)
                self.assertEqual(national_mock.call_count,3);self.assertEqual(details_mock.call_count,105)
                self.assertEqual(runner.main(),0)
                self.assertEqual(national_mock.call_count,3);self.assertEqual(details_mock.call_count,105)
            with Session(engine) as db:
                self.assertEqual(db.scalar(select(func.count(DailyObservation.id))),102)
                self.assertEqual(db.scalar(select(func.count(Dataset.id))),612)
                self.assertIsNone(db.get(CollectionControl,'dvcqg').lease_locked_by)
            engine.dispose()

if __name__=='__main__':unittest.main()
