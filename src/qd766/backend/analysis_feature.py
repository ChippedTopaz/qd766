"""Durable independent maintenance switch; never edits prompt revisions or wallets."""
from sqlalchemy import inspect
from fastapi import HTTPException
from .models import AnalysisFeatureControl

UNAVAILABLE='Tính năng tạm thời không khả dụng do đang trong quá trình nâng cấp.'

def verify_schema(engine):
    inspector=inspect(engine)
    if not inspector.has_table('analysis_feature_control'):
        raise ValueError('Analysis feature-control migration required')
    if not set(AnalysisFeatureControl.__table__.columns.keys())<={c['name'] for c in inspector.get_columns('analysis_feature_control')}:
        raise ValueError('Analysis feature-control schema incomplete')

def feature_state(db):
    ready=inspect(db.connection()).has_table('analysis_feature_control')
    row=db.get(AnalysisFeatureControl,1,populate_existing=True) if ready else None
    return {'enabled':row.enabled if row else ready,'revision':row.revision if row else 0,'schemaReady':ready}

def require_available(db):
    if not feature_state(db)['enabled']:raise HTTPException(503,UNAVAILABLE)
