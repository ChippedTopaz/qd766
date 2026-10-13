import unittest,uuid
from datetime import timedelta
import test_challenges
from qd766.backend.payment_reference import attach_payment_reference
from qd766.backend.models import Entity
from qd766.backend.agency_scope import restrict_agency

class PaymentReferenceTests(unittest.TestCase):
 def setUp(self):self.f=test_challenges.ChallengeTests();self.f.setUp()
 def tearDown(self):self.f.tearDown()
 def test_same_period_agency_reference_read_only_and_scope(self):
  with self.f.factory.begin() as db:
   general=self.f.snapshot(db)
   payment=general.datasets[-1]
   for e in payment.entities:e.parameters={'totalFeeDossierFormality':8,'totalFeeFormality':40,'totalDossierOnlineFormalityPaymentSuccess':18,'totalFeeDossierFormalityDistinct':40}
   db.flush()
   selected=self.f.snapshot(db,captured=general.created_at+timedelta(hours=1));selected.scope='formality';selected.formality_id=uuid.uuid4();db.flush()
   future=self.f.snapshot(db,captured=selected.created_at+timedelta(hours=1))
   for e in future.datasets[-1].entities:e.parameters={'totalFeeFormality':999}
   db.flush()
   payload={'scope':'formality','datasets':[{'group':'formality-online-payment-tree','root':{'departmentId':str(self.f.root),'parameters':{}},'children':[
    {'departmentId':str(self.f.units[i]),'departmentLevel':'COMMUNE','parameters':{'totalFeeFormality':1},'metrics':[]} for i in (0,1)]}]}
   raw={'totalFeeFormality':1};payload['datasets'][0]['children'][0]['parameters']=raw
   attach_payment_reference(db,selected,payload)
   child=payload['datasets'][0]['children'][0]
   self.assertEqual(child['parameters']['agencyPaymentProvidedDenominator'],40)
   self.assertEqual(child['parameters']['totalFeeFormality'],1,'Do not overwrite procedure parameters')
   self.assertEqual(raw,{'totalFeeFormality':1},'Do not mutate aliased source JSON')
   self.assertNotIn('agencyPaymentProvidedDenominator',selected.datasets[-1].entities[0].parameters)
   scoped=restrict_agency({'snapshot':payload},self.f.units[0])['snapshot']['datasets'][0]
   self.assertEqual(scoped['children'][0]['parameters']['agencyPaymentTransactionsNumerator'],18)
   self.assertEqual(scoped['children'][1]['parameters'],{},'No other agency detail exposure')
 def test_all_scope_and_missing_reference_are_unchanged(self):
  with self.f.factory.begin() as db:
   selected=self.f.snapshot(db);payload={'datasets':[]}
   attach_payment_reference(db,selected,payload);self.assertEqual(payload,{'datasets':[]})
   selected.scope='formality';selected.formality_id=uuid.uuid4();db.flush()
   attach_payment_reference(db,selected,payload);self.assertEqual(payload,{'datasets':[]})
