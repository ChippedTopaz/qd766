import json
import uuid
from contextlib import contextmanager
import threading
import time
import unittest
from pathlib import Path
from test_collection import response_for, ROOT_ID
from qd766.collection import plan_evaluation_requests, CollectionError, SafetyStop, TransportResponse
from qd766.concurrent_collection import collect_concurrent_snapshot
from qd766.periods import PeriodSelection
TEST_TEMP=Path(__file__).resolve().parents[1]/'.tmp-release-preflight'

@contextmanager
def test_directory():
    # tempfile's Windows restrictive ACLs are incompatible with this sandbox.
    path=TEST_TEMP/('concurrent-test-'+uuid.uuid4().hex)
    path.mkdir(parents=True)
    yield path

class ConcurrentCollectionTests(unittest.TestCase):
    def setUp(self):
        self.period=PeriodSelection('month',2026,9)
        self.plan=plan_evaluation_requests(self.period,ROOT_ID)

    def test_formality_processor_uses_pool_and_omits_unsupported_group(self):
        from unittest.mock import patch,MagicMock
        from qd766.backend.worker import EvaluationSnapshotProcessor
        import uuid
        processor=EvaluationSnapshotProcessor(collection_root=TEST_TEMP,transport=object(),max_workers=3,max_retries=4)
        normalized=MagicMock()
        normalized.to_dict.return_value={'checked':True}
        request={'kind':'evaluation-snapshot','rootDepartmentId':ROOT_ID,
            'period':{'type':'month','year':2026,'month':9},'scope':'formality',
            'formalityId':str(uuid.uuid4())}
        with patch('qd766.concurrent_collection.collect_concurrent_snapshot') as collect,patch('qd766.backend.worker.build_collected_snapshot',return_value=normalized):
            result=processor(uuid.uuid4(),request)
        self.assertEqual(result,{'checked':True})
        plan=collect.call_args.args[0]
        self.assertEqual(len(plan),5)
        self.assertNotIn('handling-satisfaction',[r.group for r in plan])
        self.assertEqual(collect.call_args.kwargs['max_workers'],3)

    def test_bounded_concurrency_and_resume(self):
        class Transport:
            active=0
            peak=0
            calls=0
            lock=threading.Lock()
            def post_json(inner,url,payload):
                with inner.lock:
                    inner.active+=1
                    inner.peak=max(inner.peak,inner.active)
                    inner.calls+=1
                time.sleep(.02)
                with inner.lock:
                    inner.active-=1
                return response_for(url.rsplit('/',1)[1])
        transport=Transport()
        with test_directory() as temp:
            options=dict(period=self.period,output_dir=Path(temp),transport=transport,max_workers=3)
            result=collect_concurrent_snapshot(self.plan,**options)
            self.assertEqual(result['status'],'complete')
            self.assertEqual(transport.peak,3)
            collect_concurrent_snapshot(self.plan,**options)
            self.assertEqual(transport.calls,6)

    def test_sustained_20_jobs_never_exceed_three_source_requests(self):
        class Transport:
            active=0
            peak=0
            calls=0
            lock=threading.Lock()
            def post_json(inner,url,payload):
                with inner.lock:
                    inner.active+=1
                    inner.peak=max(inner.peak,inner.active)
                    inner.calls+=1
                try:
                    time.sleep(.005)
                    return response_for(url.rsplit('/',1)[1])
                finally:
                    with inner.lock:
                        inner.active-=1
        transport=Transport()
        with test_directory() as temp:
            for index in range(20):
                manifest=collect_concurrent_snapshot(self.plan,period=self.period,
                    output_dir=temp/str(index),transport=transport,max_workers=3)
                self.assertEqual(manifest['status'],'complete')
        self.assertEqual(transport.calls,120)
        self.assertLessEqual(transport.peak,3)
        self.assertEqual(transport.active,0)

    def test_failure_preserves_other_groups_and_only_retries_missing(self):
        class Transport:
            fail=True
            calls=[]
            def post_json(inner,url,payload):
                group=url.rsplit('/',1)[1]
                inner.calls.append(group)
                return response_for(group,status=500 if inner.fail and group=='transparency' else 201)
        transport=Transport()
        with test_directory() as temp:
            options=dict(period=self.period,output_dir=Path(temp),transport=transport,max_retries=1,sleeper=lambda _:None)
            with self.assertRaises(CollectionError):
                collect_concurrent_snapshot(self.plan,**options)
            self.assertEqual(len(json.loads((Path(temp)/'manifest.json').read_text())['captures']),5)
            transport.fail=False
            transport.calls=[]
            collect_concurrent_snapshot(self.plan,**options)
            self.assertEqual(transport.calls,['transparency'])

    def test_rejection_stops(self):
        class Transport:
            def post_json(inner,url,payload):
                return response_for(url.rsplit('/',1)[1],status=403)
        with test_directory() as temp:
            with self.assertRaises(SafetyStop):
                collect_concurrent_snapshot(self.plan,period=self.period,output_dir=Path(temp),transport=Transport())

    def test_checkpoint_corruption_rejected(self):
        class Transport:
            def post_json(inner,url,payload):
                return response_for(url.rsplit('/',1)[1])
        with test_directory() as temp:
            options=dict(period=self.period,output_dir=Path(temp),transport=Transport())
            collect_concurrent_snapshot(self.plan,**options)
            (Path(temp)/'transparency.json').write_text('{}')
            with self.assertRaises(CollectionError):
                collect_concurrent_snapshot(self.plan,**options)

    def test_pages_assembled_and_identity_validated(self):
        class Transport:
            def post_json(inner,url,payload):
                response=response_for('transparency')
                raw=json.loads(response.body)
                raw['data']['pagination']={'totalPages':2}
                raw['data']['evaluation'][0]['departmentId']=f"child-{payload['currentPage']}"
                return TransportResponse(201,json.dumps(raw).encode(),'application/json')
        with test_directory() as temp:
            collect_concurrent_snapshot(self.plan[:1],period=self.period,output_dir=Path(temp),transport=Transport())
            raw=json.loads((Path(temp)/'transparency.json').read_text())
            self.assertEqual(len(raw['data']['evaluation']),2)
