"""Offline SQL injection and access regression checks; only in-memory SQLite."""
import ast
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from qd766.backend.app import create_app
from qd766.backend.auth import digest
from qd766.backend.config import Settings
from qd766.backend.importer import store_normalized_snapshot
from qd766.backend.models import Base, Department, Formality, LoginSession, UserAccount, CollectionJob, PaidDataRequest, AccountCollectionPermission
from test_backend import ROOT_ID, CHILD_ID, TAY_NINH_ROOT_ID, TAY_NINH_CHILD_ID, snapshot_payload


def unsafe_raw_sql(source):
    """Guard direct raw SQL construction; does not replace API/runtime review."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
        first = node.args[0]
        if name in {"text", "exec_driver_sql", "literal_column"} and not (
                isinstance(first, ast.Constant) and isinstance(first.value, str)):
            found.append(node.lineno)
        if name == "execute" and isinstance(first, (ast.JoinedStr, ast.BinOp)):
            found.append(node.lineno)
    return found


class SqlInjectionTests(unittest.TestCase):
    def test_csrf_comparison_rejects_empty_and_malformed_tokens(self):
        from qd766.backend.auth import csrf_matches
        self.assertTrue(csrf_matches("valid-token","valid-token"))
        for supplied, expected in (("",""),("","valid"),("é","valid"),("\ud800","valid")):
            self.assertFalse(csrf_matches(supplied,expected))

    def test_backend_raw_sql_is_constant(self):
        offenders = {}
        for path in (ROOT / "src/qd766/backend").glob("*.py"):
            lines = unsafe_raw_sql(path.read_text(encoding="utf-8"))
            if lines:
                offenders[path.name] = lines
        self.assertEqual(offenders, {})

    def test_guard_detects_dynamic_raw_sql(self):
        for source in ('text(f"SELECT {user}")', 'text("SELECT " + user)',
                       'db.exec_driver_sql(sql)', 'db.execute(f"SELECT {user}")',
                       'literal_column(user)'):
            self.assertTrue(unsafe_raw_sql(source), source)
        self.assertEqual(unsafe_raw_sql('text("SELECT * FROM t WHERE code=:code")'), [])

    def test_formality_code_is_bound_literal_not_executable_sql(self):
        app = create_app(Settings(database_url="sqlite+pysqlite://"))
        Base.metadata.create_all(app.state.engine)
        payloads = ["' OR 1=1 --", "'; DROP TABLE formalities; --", "x' UNION SELECT 1 --"]
        try:
            with app.state.session_factory.begin() as db:
                db.add(Formality(id=uuid.uuid4(), code="SAFE", name="Safe", attributes={}))
                for index, payload in enumerate(payloads):
                    db.add(Formality(id=uuid.uuid4(), code=payload, name=f"Literal {index}", attributes={}))
            queries = []
            def capture(connection, cursor, statement, parameters, context, executemany):
                queries.append((statement, parameters))
            event.listen(app.state.engine, "before_cursor_execute", capture)
            with TestClient(app) as client:
                for payload in payloads:
                    queries.clear()
                    response = client.get("/api/v1/formalities", params={"code": payload})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual([row["code"] for row in response.json()], [payload])
                    self.assertTrue(any(payload in str(parameters) for _, parameters in queries))
                    self.assertTrue(all(payload not in statement for statement, _ in queries))
                for params in ({"department_id":payloads[0]}, {"limit":payloads[0]}, {"limit":201}):
                    self.assertEqual(client.get("/api/v1/formalities", params=params).status_code, 422)
            with app.state.session_factory() as db:
                self.assertEqual(db.scalar(select(func.count()).select_from(Formality)), 4)
        finally:
            app.state.engine.dispose()


class SecurityBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Settings(database_url="sqlite+pysqlite://", public_read_only=True,
            require_login=True, invite_required=True, paid_requests_enabled=True, formality_credit_cost=5,
            google_client_id="test", google_client_secret="fake-test-secret",
            google_redirect_uri="https://testserver/api/v1/auth/google/callback"))
        Base.metadata.create_all(self.app.state.engine)
        self.app.state.province_catalog_client = SimpleNamespace(load=lambda *a, **kw: self.fail("No upstream call allowed"))
        self.client = TestClient(self.app, base_url="https://testserver")
        self.identity = uuid.uuid4()
        with self.app.state.session_factory.begin() as db:
            store_normalized_snapshot(db, snapshot_payload())
            store_normalized_snapshot(db, snapshot_payload(root_id=TAY_NINH_ROOT_ID, child_id=TAY_NINH_CHILD_ID))
            db.add(UserAccount(id=self.identity, external_subject="google:security-test", display_name="Test",
                role="user", active=True, trial_admitted=True, access_tier="agency",
                root_department_id=uuid.UUID(ROOT_ID), unit_department_id=uuid.UUID(CHILD_ID)))
            db.flush()
            db.add(AccountCollectionPermission(account_id=self.identity, enabled=True))
            db.add(LoginSession(token_hash=digest("security-session"), account_id=self.identity,
                csrf_token="security-csrf", expires_at=datetime.now(timezone.utc)+timedelta(hours=1)))
        self.client.cookies.set("qd766_session", "security-session")

    def tearDown(self):
        self.client.close()
        self.app.state.engine.dispose()

    def test_agency_cannot_broaden_root_or_units_using_duplicate_parameters(self):
        for values in ([TAY_NINH_ROOT_ID], [ROOT_ID,TAY_NINH_ROOT_ID], [TAY_NINH_ROOT_ID,ROOT_ID], ["' OR 1=1 --"]):
            response = self.client.get("/api/v1/dashboard", params=[("root_department_id",v) for v in values])
            self.assertEqual(response.status_code, 403)
        response = self.client.get("/api/v1/dashboard", params={"unit_department_id":TAY_NINH_CHILD_ID})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([row["departmentId"] for row in response.json()["units"]], [CHILD_ID])

    def test_user_cannot_admin_or_operator_even_with_valid_csrf(self):
        for path in ("accounts", "invitations", "audit", "directory"):
            self.assertEqual(self.client.get("/api/v1/admin/"+path).status_code,403)
        for path in ("collection-control", "province-batches", "dashboard/requests"):
            self.assertEqual(self.client.post("/api/v1/"+path,json={},headers={"X-QD766-CSRF":"security-csrf"}).status_code,403)
        self.assertEqual(self.client.post("/api/v1/admin/accounts/"+str(self.identity),
            json={"role":"admin"},headers={"X-QD766-CSRF":"security-csrf"}).status_code,403)

    def test_group_export_is_strictly_limited_to_assigned_agency(self):
        params={"period_type":"month","year":2026,"period_value":8,"root_department_id":ROOT_ID}
        response=self.client.get('/api/v1/dashboard/group-export',params=params)
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body['accessScope'],'agency')
        self.assertEqual([unit['departmentId'] for unit in body['units']],[CHILD_ID])
        self.assertEqual(len(body['groups']),6)
        for group in body['groups']:
            self.assertTrue(all(entity['departmentId']==CHILD_ID for entity in group['entities']))
        self.assertNotIn('raw',response.text)
        self.assertNotIn(TAY_NINH_CHILD_ID,response.text)
        for change in ({'root_department_id':TAY_NINH_ROOT_ID},{'unit_department_id':TAY_NINH_CHILD_ID}):
            self.assertEqual(self.client.get('/api/v1/dashboard/group-export',params=params|change).status_code,403)
        self.assertEqual(self.client.get('/api/v1/dashboard/group-export',params=params|{'group':'invalid'}).status_code,422)
        self.assertEqual(self.client.get('/api/v1/dashboard/group-export',params=params|{'period_value':13}).status_code,422)

    def test_group_export_province_and_national_are_not_admin_roles(self):
        params={"period_type":"month","year":2026,"period_value":8,"root_department_id":ROOT_ID,'group':'transparency'}
        for tier in ('province','national'):
            with self.app.state.session_factory.begin() as db:
                account=db.get(UserAccount,self.identity);account.access_tier=tier;account.unit_department_id=None
            response=self.client.get('/api/v1/dashboard/group-export',params=params)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual({unit['departmentId'] for unit in response.json()['units']},{ROOT_ID,CHILD_ID})
            self.assertEqual(len(response.json()['groups']),1)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)

    def test_group_export_requires_session_and_owned_formality(self):
        params={"period_type":"month","year":2026,"period_value":8,"root_department_id":ROOT_ID}
        self.assertEqual(self.client.get('/api/v1/dashboard/group-export',params=params|{'scope':'formality','formality_id':str(uuid.uuid4())}).status_code,403)
        self.assertEqual(self.client.post('/api/v1/dashboard/group-export',json=params).status_code,403)
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/v1/dashboard/group-export',params=params).status_code,401)

    def test_bad_confirmation_and_csrf_cannot_create_job(self):
        for headers in ({}, {"X-QD766-CSRF":"' OR 1=1 --"}, {"X-QD766-CSRF":"security-csrf"}):
            response=self.client.post("/api/v1/me/formality-requests",
                json={"quote":"' OR 1=1 --", "token":str(uuid.uuid4())},headers=headers)
            expected=409 if headers.get("X-QD766-CSRF")=="security-csrf" else 403
            self.assertEqual(response.status_code,expected)
        with self.app.state.session_factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(CollectionJob)),0)
            self.assertEqual(db.scalar(select(func.count()).select_from(PaidDataRequest)),0)

    def test_locked_and_fake_sessions_fail_closed(self):
        self.client.cookies.set("qd766_session","' OR 1=1 --")
        self.assertEqual(self.client.get("/api/v1/dashboard").status_code,401)
        self.client.cookies.set("qd766_session","security-session")
        with self.app.state.session_factory.begin() as db:
            db.get(UserAccount,self.identity).active=False
        self.assertEqual(self.client.get("/api/v1/dashboard").status_code,401)

    def test_non_ascii_csrf_rejects_without_internal_error(self):
        headers={"X-QD766-CSRF":b"\xe9"}
        self.assertEqual(self.client.post("/api/v1/auth/logout",headers=headers).status_code,403)
        self.assertEqual(self.client.post("/api/v1/me/formality-requests",headers=headers,
            json={"quote":"invalid", "token":str(uuid.uuid4())}).status_code,403)
        with self.app.state.session_factory.begin() as db:
            db.get(UserAccount,self.identity).role="admin"
        self.assertEqual(self.client.post("/api/v1/admin/invitations",json={},headers=headers).status_code,403)


if __name__ == "__main__":
    unittest.main()
