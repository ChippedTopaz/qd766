import copy
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from qd766.backend.agency_scope import restrict_agency, comparison_points


class AgencyComparisonProjectionTests(unittest.TestCase):
    def test_payment_three_points_no_peer_counts_and_reference_scope(self):
        parameters={'totalFeeDossierFormality':8,'totalFeeFormality':40,
            'totalDossierOnlineFormalityPaymentSuccess':18,'totalFeeDossierFormalityDistinct':40,
            'totalDossierOnlinePaymentSuccess':80,'totalDossierFinancialObligation':100}
        expected={'payment:3.5':{'score':.5,'maximum':2},'payment:3.5b':{'score':1.13,'maximum':2},'payment:3.6':{'score':4.8,'maximum':6}}
        peer={'departmentId':'other','departmentLevel':'COMMUNE','parameters':parameters,'metrics':[]}
        own={**peer,'departmentId':'own'}
        source={'snapshot':{'scope':'all','datasets':[{'group':'formality-online-payment-tree','root':{},'children':[own,peer]}]}}
        before=copy.deepcopy(source)
        result=restrict_agency(source,'own')['snapshot']['datasets'][0]['children'][1]
        self.assertEqual(result['comparisonPoints'],expected);self.assertEqual(result['parameters'],{});self.assertEqual(result['metrics'],[])
        self.assertEqual(source,before)
        params={**parameters,'totalFeeDossierFormality':1,'totalFeeFormality':1,
            'agencyPaymentProvidedNumerator':8,'agencyPaymentProvidedDenominator':40,
            'agencyPaymentTransactionsNumerator':18,'agencyPaymentTransactionsDenominator':40}
        self.assertEqual(comparison_points({'parameters':params},'formality-online-payment-tree','formality'),expected)
        self.assertEqual(comparison_points({'parameters':parameters},'formality-online-payment-tree','formality'),{'payment:3.6':expected['payment:3.6']})
        for value in (None,True,float('nan'),float('inf'),-1,41):
            with self.subTest(value=value):
                invalid={**parameters,'totalFeeDossierFormality':value}
                self.assertNotIn('payment:3.5',comparison_points({'parameters':invalid},'formality-online-payment-tree'))
        self.assertEqual(comparison_points({'parameters':{**parameters,'totalFeeDossierFormality':0}},'formality-online-payment-tree')['payment:3.5']['score'],0)
    def test_score_projection_preserves_comparison_without_business_data(self):
        peer={'departmentId':'other','departmentLevel':'COMMUNE','apiScore':8,'apiMaxScore':22,'metrics':[
            {'code':'digitized','name':'Số hóa','apiScore':.56,'apiMaxScore':4,
             'numerator':18139,'denominator':130254,'ratio':13.9,'extras':{'private':True}}],
            'parameters':{'totalReceived':130254,'private':'secret'}}
        own=copy.deepcopy(peer);own['departmentId']='own'
        source={'snapshot':{'datasets':[{'group':'dossier-digitized','root':copy.deepcopy(peer),
            'children':[own,peer]}]}}
        original=copy.deepcopy(source)
        projected=restrict_agency(source,'own')['snapshot']['datasets'][0]
        other=projected['children'][1]
        self.assertEqual(other['comparisonPoints'],{'raw:digitized':{'score':.56,'maximum':4}})
        self.assertEqual(other['metrics'],[]);self.assertEqual(other['parameters'],{})
        self.assertTrue(projected['children'][0]['metrics'])
        self.assertNotIn('comparisonPoints',projected['root'])
        self.assertEqual(source,original)
        self.assertEqual(restrict_agency(source,None),source)

    def test_progress_reference_score_matches_frontend_without_counts(self):
        peer={'departmentId':'other','departmentLevel':'COMMUNE','metrics':[],'parameters':{'totalReceived':100,'totalOnTime':80,'totalOverdue':20},'apiMaxScore':20}
        source={'snapshot':{'datasets':[{'group':'dvc-progress-tree','root':{},'children':[peer,{'departmentId':'own','departmentLevel':'COMMUNE'}]}]}}
        result=restrict_agency(source,'own')['snapshot']['datasets'][0]['children'][0]
        self.assertEqual(result['comparisonPoints']['progress:on-time']['score'],16)
        self.assertEqual(result['parameters'],{})
        peer['parameters']['totalOverdue']=21
        invalid=restrict_agency(source,'own')['snapshot']['datasets'][0]['children'][0]
        self.assertNotIn('progress:on-time',invalid['comparisonPoints'])

    def test_unknown_scores_are_not_zero(self):
        peer={'departmentId':'other','departmentLevel':'COMMUNE','metrics':[{'code':'missing','name':'Missing','apiScore':None}],
              'parameters':{'totalReceived':0,'totalOnTime':0},'apiMaxScore':20}
        source={'snapshot':{'datasets':[{'group':'dvc-progress-tree','root':{},'children':[peer,{'departmentId':'own','departmentLevel':'COMMUNE'}]}]}}
        self.assertEqual(restrict_agency(source,'own')['snapshot']['datasets'][0]['children'][0]['comparisonPoints'],{})

    def test_other_levels_and_unknown_membership_get_no_new_scores(self):
        peer={'departmentId':'other','departmentLevel':'PROVINCE','parameters':{},
              'metrics':[{'code':'x','name':'X','apiScore':1,'apiMaxScore':4}]}
        own={'departmentId':'own','departmentLevel':'COMMUNE'}
        source={'snapshot':{'datasets':[{'group':'dossier-digitized','root':{},'children':[peer,own]}]}}
        self.assertEqual(restrict_agency(source,'own')['snapshot']['datasets'][0]['children'][0]['comparisonPoints'],{})
        source['snapshot']['datasets'][0]['children'].remove(own)
        self.assertEqual(restrict_agency(source,'own')['snapshot']['datasets'][0]['children'][0]['comparisonPoints'],{})
