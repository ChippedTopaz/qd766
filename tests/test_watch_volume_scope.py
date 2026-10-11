import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from qd766.backend.agency_scope import restrict_agency

class WatchVolumeScopeTest(unittest.TestCase):
    def test_only_eligibility_boolean_survives_redaction(self):
        def entity(id,volume):return dict(departmentId=id,departmentLevel='COMMUNE',parameters={'totalReceived':volume,'private':'secret'},metrics=[])
        payload={'snapshot':{'scope':'all','datasets':[{'group':'dvc-progress-tree','root':entity('root',1000),'children':[entity('own',100),entity('min',80),entity('max',120),entity('below',79),entity('above',121),entity('missing',None)]}]}}
        result=restrict_agency(payload,'own')['snapshot']['datasets'][0]
        for peer in result['children'][1:]:
            self.assertEqual(peer['parameters'],{})
            self.assertEqual(peer['similarReceivedVolume'],None if peer['departmentId']=='missing' else peer['departmentId'] in ['min','max'])
        self.assertEqual(payload['snapshot']['datasets'][0]['children'][1]['parameters']['totalReceived'],80,'Shared cache unchanged')
        payload['snapshot']['scope']='formality'
        result=restrict_agency(payload,'own')['snapshot']['datasets'][0]
        self.assertTrue(all('similarReceivedVolume' not in e for e in result['children']))
