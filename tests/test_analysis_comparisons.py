import unittest,uuid
from datetime import timedelta
from sqlalchemy import select
import test_gemini_analysis as fixture
from qd766.backend.models import Department,Snapshot,Dataset,Entity
from qd766.backend.analysis import source_evidence,AnalysisSelection
from qd766.backend.analysis_comparisons import within_volume,previous_periods

class ComparisonTest(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PaidAnalysisTest();self.f.setUp();self.unit=uuid.uuid4()
        with self.f.factory.begin() as db:db.add(Department(id=self.unit,name='Xã A',department_level='COMMUNE'))
    def tearDown(self):self.f.tearDown()
    def snapshot(self,month,*,maximum=20,score=15,volume=100,offset=0,root=None,units=(),version=None,kind='child'):
        with self.f.factory.begin() as db:
            snap=Snapshot(snapshot_key=str(uuid.uuid4()),schema_version=1,root_department_id=root or self.f.root,
                period_type='month',year=2026,period_value=month,scope='all',state='complete',
                created_at=self.f.now+timedelta(seconds=offset),policy={'formulaVersion':version} if version else {})
            db.add(snap);db.flush()
            dataset=Dataset(snapshot_id=snap.id,position=0,group_name='dvc-progress-tree',schema_kind='parameters',
                formula_status='verified',score_policy='api-authoritative',raw_path='private',raw_sha256='a'*64)
            db.add(dataset);db.flush()
            values=[(self.unit,volume,score,kind),*units]
            for i,(unit,received,points,kind) in enumerate(values):
                db.add(Entity(dataset_id=dataset.id,department_id=unit,entity_kind=kind,position=i,
                    api_score=points,api_max_score=maximum,score_source='dvcqg-api',
                    parameters={'totalReceived':received,'totalOnTime':received,'totalOverdue':0,'secret':'DO_NOT_SEND'}))
            return snap.id
    def evidence(self,month=8):
        with self.f.factory() as db:
            return source_evidence(db,AnalysisSelection(rootDepartmentId=self.f.root,unitId=self.unit,
                periodType='month',year=2026,periodValue=month,groupIds=['dvc-progress-tree']))
    def test_exact_previous_periods_missing_gap_and_no_future_capture(self):
        self.snapshot(8,offset=0);self.snapshot(7,score=17,offset=-1)
        self.snapshot(5,score=18,offset=-2)
        self.snapshot(7,score=1,offset=1) # Must not use capture newer than the analyzed snapshot.
        comparison=self.evidence()['comparisons']['dvc-progress-tree']
        self.assertEqual([row['periodValue'] for row in comparison['periods']],[7,6,5])
        self.assertEqual(comparison['periods'][0]['delta'],-2)
        self.assertFalse(comparison['periods'][1]['available'])
        self.assertEqual(comparison['periods'][2]['delta'],-3)
        self.assertIn('comparison',{card['id'].split(':')[-1] for card in self.evidence()['findings']})
    def test_strict_level_and_inclusive_volume_boundaries(self):
        ids=[uuid.uuid4() for _ in range(6)]
        with self.f.factory.begin() as db:
            for i,key in enumerate(ids):db.add(Department(id=key,name='PRIVATE_PEER_NAME',department_level='PROVINCE' if i==4 else 'COMMUNE'))
        units=[(ids[0],80,14,'child'),(ids[1],120,18,'child'),(ids[2],79,1,'child'),
               (ids[3],121,2,'child'),(ids[4],100,3,'child'),(ids[5],100,4,'root')]
        self.snapshot(8,units=units)
        evidence=self.evidence();peer=evidence['comparisons']['dvc-progress-tree']['peers']
        self.assertEqual(peer['count'],2);self.assertEqual(peer['medianScore'],16)
        self.assertEqual(peer['gapToMedian'],-1);self.assertEqual(peer['targetRank'],2)
        self.assertEqual(peer['minimumReceived'],80);self.assertEqual(peer['maximumReceived'],120)
        self.assertNotIn('PRIVATE_PEER_NAME',str(evidence));self.assertNotIn('DO_NOT_SEND',str(evidence))
        self.assertEqual(len(evidence['groups']),1)
    def test_changed_maximum_or_formula_version_not_compared(self):
        self.snapshot(8,version='new');self.snapshot(7,version='old',offset=-1)
        self.snapshot(6,maximum=18,version='new',offset=-2)
        rows=self.evidence()['comparisons']['dvc-progress-tree']['periods']
        self.assertFalse(rows[0]['comparable']);self.assertFalse(rows[1]['comparable'])
        self.assertIsNone(rows[0]['group']);self.assertIsNone(rows[0]['delta'])
    def test_province_roots_require_same_capture_day_version_and_volume(self):
        self.unit=self.f.root
        self.snapshot(8,version='new',kind='root')
        ids=[uuid.uuid4() for _ in range(5)]
        with self.f.factory.begin() as db:
            for key in ids:db.add(Department(id=key,name='OTHER_PROVINCE_PRIVATE',department_level='PROVINCE'))
        target=self.unit
        # One valid peer, prior-day peer, newer capture, other formula and other volume.
        for key,offset,version,volume in zip(ids,[-1,-86400,1,-2,-3],['new','new','new','old','new'],[100,100,100,100,121]):
            self.unit=key
            self.snapshot(8,root=key,offset=offset,version=version,volume=volume,kind='root',score=18)
        self.unit=target
        evidence=self.evidence();peer=evidence['comparisons']['dvc-progress-tree']['peers']
        self.assertEqual(peer['scope'],'province-roots-same-capture-day')
        self.assertEqual(peer['count'],1);self.assertEqual(peer['medianScore'],18)
        self.assertNotIn('OTHER_PROVINCE_PRIVATE',str(evidence))
    def test_missing_and_zero_volume_do_not_fabricate_peer_comparison(self):
        self.snapshot(8,volume=0)
        peer=self.evidence()['comparisons']['dvc-progress-tree']['peers']
        self.assertEqual(peer['count'],0);self.assertIn('reason',peer)
    def test_unavailable_selected_group_rejected_before_hold(self):
        from fastapi import HTTPException
        self.snapshot(8)
        with self.f.factory() as db:
            with self.assertRaises(HTTPException) as caught:
                source_evidence(db,AnalysisSelection(rootDepartmentId=self.f.root,unitId=self.unit,
                    periodType='month',year=2026,periodValue=8,groupIds=['dossier-digitized']))
            self.assertEqual(caught.exception.status_code,409)
    def test_calendar_rollovers_and_volume_precision(self):
        for kind,value,expected in [('month',1,(2025,12)),('quarter',1,(2025,4)),('year',None,(2025,None))]:
            snap=type('Period',(),{'period_type':kind,'year':2026,'period_value':value})()
            first=next(previous_periods(snap));self.assertEqual((first.year,first.value),expected)
        self.assertTrue(within_volume(100,80));self.assertTrue(within_volume(100,120))
        self.assertFalse(within_volume(100,79));self.assertFalse(within_volume(100,121))
        self.assertFalse(within_volume(0,0));self.assertFalse(within_volume(None,100))
        self.assertTrue(within_volume(1000000000001,1000000000001))

if __name__=='__main__':unittest.main()
