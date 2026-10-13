"""Read-only same-agency payment reference for a single-procedure snapshot."""
from sqlalchemy import select
from .models import Snapshot,Dataset,Entity

REFERENCE_KEYS={
    'agencyPaymentProvidedNumerator':'totalFeeDossierFormality',
    'agencyPaymentProvidedDenominator':'totalFeeFormality',
    'agencyPaymentTransactionsNumerator':'totalDossierOnlineFormalityPaymentSuccess',
    'agencyPaymentTransactionsDenominator':'totalFeeDossierFormalityDistinct',
}

def attach_payment_reference(session,selected,payload):
    if selected.scope!='formality':return
    reference=select(Snapshot.id).where(Snapshot.root_department_id==selected.root_department_id,
        Snapshot.scope=='all',Snapshot.state=='complete',Snapshot.period_type==selected.period_type,
        Snapshot.year==selected.year,Snapshot.created_at<=selected.created_at)
    reference=reference.where(Snapshot.period_value.is_(None) if selected.period_value is None else Snapshot.period_value==selected.period_value)
    reference_id=session.scalar(reference.order_by(Snapshot.created_at.desc(),Snapshot.id.desc()).limit(1))
    if reference_id is None:return
    rows=session.execute(select(Entity.department_id,Entity.parameters).join(Dataset,Entity.dataset_id==Dataset.id).where(
        Dataset.snapshot_id==reference_id,Dataset.group_name=='formality-online-payment-tree')).all()
    parameters={str(unit):values or {} for unit,values in rows}
    for dataset in payload.get('datasets',[]):
        if dataset.get('group')!='formality-online-payment-tree':continue
        for entity in [dataset.get('root',{}),*dataset.get('children',[])]:
            source=parameters.get(entity.get('departmentId'),{})
            entity['parameters']={**(entity.get('parameters') or {}),**{key:source.get(value) for key,value in REFERENCE_KEYS.items()}}
