"""Read-only HTTP-contract check using office PostgreSQL, no network listener."""
import json
import sys
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from qd766.backend import create_app
from qd766.backend.config import Settings,load_environment_file
from qd766.backend.database import create_database_engine
from qd766.province_roots import load_province_roots


def main():
    load_environment_file(ROOT/".env")
    engine=create_database_engine(Settings.from_env())
    app=create_app(Settings(database_url="sqlite+pysqlite://",public_read_only=True))
    checks=[]
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                app.state.session_factory=sessionmaker(bind=connection,autoflush=False,
                    join_transaction_mode="create_savepoint")
                client=TestClient(app)
                root=next(item for item in load_province_roots().values() if item.province_name=="Phú Thọ")
                response=client.get("/api/v1/dashboard",params={"root_department_id":str(root.root_department_id)})
                assert response.status_code==200
                assert len([key for key in response.json()["snapshots"] if key.endswith(":all")])==15
                for kind, values in (("month",range(1,11)),("quarter",range(1,5)),("year",[None])):
                    for value in values:
                        params={"period_type":kind,"year":2026,"scope":"all","root_department_id":str(root.root_department_id)}
                        if value is not None:params["period_value"]=value
                        selected=client.get("/api/v1/dashboard/selection",params=params)
                        assert selected.status_code==200
                        snapshot=selected.json()["snapshot"]
                        assert len(snapshot["datasets"])==6
                        ranks=client.get("/api/v1/dashboard/province-rankings",params=params)
                        assert ranks.status_code==200 and len(ranks.json())==34
                        summary_only=snapshot["delivery"].get("detailsAvailable") is False
                        if summary_only:
                            assert snapshot["delivery"]["detailsCapturedAt"] is None
                            assert all(not dataset["children"] and not dataset["root"]["metrics"]
                                and not dataset["root"]["parameters"] for dataset in snapshot["datasets"])
                        checks.append({"type":kind,"value":value,"groups":6,"rankedProvinces":34,"summaryOnly":summary_only})
        print(json.dumps({"state":"verified-read-only","province":"Phú Thọ","checks":checks},ensure_ascii=True))
    finally:
        engine.dispose()
        app.state.engine.dispose()


if __name__=="__main__":
    main()
