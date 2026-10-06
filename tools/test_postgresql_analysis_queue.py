"""Mock-provider concurrency and migration rehearsal in a NEW isolated test schema."""
import sys,uuid,importlib.util
from pathlib import Path
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier,Event
from unittest.mock import patch
from sqlalchemy import create_engine,text
from alembic.migration import MigrationContext
from alembic.operations import Operations
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
from test_postgresql_credits import isolated_url
import test_gemini_analysis as fixture
from qd766.backend import analysis_queue as queue

def main():
    url=isolated_url(ROOT/'.env')
    assert url.database=='qd766_credit_test'
    schema='analysis_queue_test_'+uuid.uuid4().hex
    engine=create_engine(url,connect_args={'connect_timeout':5})
    with engine.begin() as connection:connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine.dispose()
    engine=create_engine(url,connect_args={'connect_timeout':5,'options':f'-c search_path={schema} -c lock_timeout=10000'},pool_size=10,max_overflow=0)
    f=fixture.PaidAnalysisTest()
    with patch.object(fixture,'create_database_engine',return_value=engine): f.setUp()
    try:
        # Rehearse exact 0018 -> 0019 DDL on an empty analysis table in TEST schema.
        with engine.begin() as connection:
            connection.execute(text('DROP TABLE analysis_queue_entries'))
            connection.execute(text('DROP INDEX ix_gemini_analysis_queue'))
            connection.execute(text('ALTER TABLE gemini_analyses DROP CONSTRAINT ck_gemini_analysis_state'))
            connection.execute(text("ALTER TABLE gemini_analyses ADD CONSTRAINT ck_gemini_analysis_state CHECK (state IN ('running','ready','failed'))"))
            path=ROOT/'alembic/versions/20261007_0019_analysis_queue.py'
            spec=importlib.util.spec_from_file_location('queue_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(connection)):module.upgrade()
        queue.verify_schema(engine)
        settings=replace(f.app.state.settings,gemini_queue_enabled=True)
        f.app.state.settings=settings
        with f.factory.begin() as db:
            for aid in f.ids:db.get(fixture.UserAccount,aid).trial_admitted=True
        first=f.post();assert first.status_code==202,first.text
        f.client.cookies.set('qd766_session','session-1')
        second=f.client.post('/api/v1/me/analysis',json={**f.body,'token':str(uuid.uuid4())},headers={'X-QD766-CSRF':'csrf-1'})
        assert second.status_code==202,second.text
        barrier=Barrier(3);release=Event()
        def generate(*_):
            barrier.wait(timeout=15);assert release.wait(15)
            return f.evidence['findings']
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures=[executor.submit(queue.run_one,f.factory,settings,generate=generate) for _ in range(2)]
            try:
                barrier.wait(timeout=15)
                with queue.provider_slot(engine) as third:assert not third,'Third PostgreSQL session must not obtain provider slot'
                assert queue.run_one(f.factory,settings,generate=lambda *_: (_ for _ in ()).throw(AssertionError('Unexpected provider call'))) is None
            finally:release.set()
            assert [future.result(timeout=15) for future in futures]==['ready','ready']
        print('POSTGRESQL_ANALYSIS_QUEUE=PASS migration=0019 concurrent=2 third_blocked=True provider=MOCK')
        print('RETAINED_TEST_SCHEMA='+schema)
    finally:f.tearDown()

if __name__=='__main__':main()
