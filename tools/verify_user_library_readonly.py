"""Check new office library against real PostgreSQL in a read-only transaction."""
import sys,json
from pathlib import Path
from sqlalchemy import text,select,func
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from qd766.backend import create_app
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine
from qd766.backend.models import Snapshot
from qd766.province_roots import load_province_roots
load_environment_file(ROOT/'.env')
engine=create_database_engine(Settings.from_env())
app=create_app(Settings(database_url='sqlite+pysqlite://'))
checks=[]
try:
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
        with conn.begin():
            conn.execute(text('SET TRANSACTION READ ONLY'))
            app.state.session_factory=sessionmaker(bind=conn,autoflush=False,join_transaction_mode='create_savepoint')
            client=TestClient(app)
            root=next(r for r in load_province_roots().values() if r.province_name=='Phú Thọ')
            for kind,value in [('year',None),('month',9),('month',10)]:
                params={'root_department_id':str(root.root_department_id),'period_type':kind,'year':2026}
                if value is not None:params['period_value']=value
                response=client.get('/api/v1/dashboard/formalities',params=params)
                assert response.status_code==200
                rows=response.json()['items']
                assert len({row['id'] for row in rows})==len(rows)
                statement=select(func.count(func.distinct(Snapshot.formality_id))).where(Snapshot.scope=='formality',
                    Snapshot.state=='complete',Snapshot.root_department_id==root.root_department_id,
                    Snapshot.period_type==kind,Snapshot.year==2026)
                statement=statement.where(Snapshot.period_value.is_(None) if value is None else Snapshot.period_value==value)
                assert len(rows)==conn.scalar(statement)
                for row in rows:
                    selected=client.get('/api/v1/dashboard/selection',params={**params,'scope':'formality','formality_id':row['id']})
                    assert selected.status_code==200
                    assert selected.json()['snapshot']['formalityId']==row['id']
                checks.append({'type':kind,'value':value,'storedFormalities':len(rows),'identityChecks':'pass'})
    print(json.dumps({'readOnly':True,'state':'verified','province':'Phú Thọ','checks':checks}))
finally:engine.dispose();app.state.engine.dispose()
