import unittest
from copy import deepcopy
from qd766.backend.agency_scope import restrict_agency

class OnlineProvinceReferenceTests(unittest.TestCase):
    def payload(self,scope='all'):
        root={'departmentId':'root','apiScore':8.5,'apiMaxScore':12,'apiRatio':70,'metrics':[{'code':'secret'}],
              'parameters':{'fullCount':21,'authorityCount':89,'privateKey':'secret','onlineDossierCount':512,'bad':float('inf')}}
        child={'departmentId':'own','departmentLevel':'COMMUNE','metrics':[], 'parameters':{},'apiScore':6}
        return {'units':[{'departmentId':'own'}], 'snapshots':{'one':{'scope':scope,'datasets':[
            {'group':group,'root':deepcopy(root),'children':[deepcopy(child)],'raw':{'path':'private'}}
            for group in ('provide-online-tree','dossier-digitized')]}}}
    def test_only_same_province_online_aggregate_allowlist(self):
        payload=self.payload();original=deepcopy(payload)
        result=restrict_agency(payload,'own');online,other=result['snapshots']['one']['datasets']
        self.assertEqual(online['provinceOnlineParameters'],{'fullCount':21,'authorityCount':89,'onlineDossierCount':512})
        self.assertNotIn('provinceOnlineParameters',other)
        for dataset in (online,other):
            self.assertEqual(dataset['root']['parameters'],{})
            self.assertEqual(dataset['root']['metrics'],[])
            self.assertIsNone(dataset['root']['apiScore'])
        self.assertEqual(payload,original)
    def test_procedure_scope_has_no_new_reference_access(self):
        result=restrict_agency(self.payload('formality'),'own')
        self.assertNotIn('provinceOnlineParameters',result['snapshots']['one']['datasets'][0])

if __name__=='__main__': unittest.main()
