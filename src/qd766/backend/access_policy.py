"""Fail-closed public preview boundary; not a replacement for account authentication."""
from fastapi import Request
from starlette.responses import JSONResponse
from .auth import current_session, SESSION_COOKIE
from sqlalchemy import select
from .models import PaidDataRequest
import uuid

AUTH_READ_PATHS = {"/api/v1/auth/google/start", "/api/v1/auth/google/callback", "/api/v1/auth/me"}
BOOTSTRAP_PATHS = {"/api/v1/access-policy", "/api/v1/health/live", "/api/v1/health/ready"}

PUBLIC_READ_PATHS = frozenset({
    "/api/v1/access-policy", "/api/v1/health/live", "/api/v1/health/ready",
    "/api/v1/dashboard", "/api/v1/dashboard/selection",
    "/api/v1/dashboard/provinces", "/api/v1/dashboard/province-rankings",
    "/api/v1/national-summaries", "/api/v1/national-summaries/latest",
})


async def enforce_public_read_only(request: Request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if path in AUTH_READ_PATHS or path in {"/api/v1/auth/logout", "/api/v1/auth/invite"}:
        allowed = request.method == "GET" if path in AUTH_READ_PATHS else request.method == "POST"
        if not allowed:
            return JSONResponse(status_code=405, content={"detail": "Method not allowed"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    if path.startswith("/api/v1/admin/"):
        # Admin handlers authenticate and check CSRF independently, including on office instances.
        from .admin import administrator
        from fastapi import HTTPException
        try:
            with request.app.state.session_factory() as db:
                administrator(request, db, write=request.method not in {"GET", "HEAD"})
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    if not request.app.state.settings.public_read_only:
        return await call_next(request)
    allowed = request.method in {"GET", "HEAD"}
    user_collection=request.app.state.settings.paid_requests_enabled
    user_path=path in {"/api/v1/me/collection-quote","/api/v1/me/formality-requests","/api/v1/me/formalities","/api/v1/me/notifications/read"}
    catalog_path=path.startswith("/api/v1/province-catalog/") and path.endswith("/preview")
    private_selection=path=="/api/v1/dashboard/selection" and request.query_params.get("scope")=="formality"
    if path.startswith("/api/"):
        allowed = allowed and path in PUBLIC_READ_PATHS
        allowed = allowed and all(value == "all" for value in request.query_params.getlist("scope"))
        allowed = allowed and not any(key.lower().replace("_", "") == "formalityid" for key in request.query_params)
        if user_collection and (user_path or catalog_path or private_selection):
            allowed=(request.method in {"GET","HEAD"} and path!="/api/v1/me/collection-quote") or (
                request.method=="POST" and path in {"/api/v1/me/collection-quote","/api/v1/me/formality-requests","/api/v1/me/notifications/read"})
    else:
        allowed = allowed and (path in {"/", "/index.html", "/admin.html", "/admin.css", "/styles.css", "/bento.css", "/collection.css"}
            or path.startswith("/dist/") and path.endswith(".js")
            or path.startswith("/vendor/") and path.endswith((".js", ".css")))
    if not allowed:
        return JSONResponse(status_code=403, content={"detail": "Chế độ dùng thử chỉ cho phép đọc dữ liệu tổng hợp. Tính năng này cần xác thực và phân quyền trước khi mở."})
    if request.app.state.settings.require_login and path.startswith("/api/") and path not in BOOTSTRAP_PATHS:
        with request.app.state.session_factory() as db:
            _, account = current_session(db, request.cookies.get(SESSION_COOKIE))
        if account is None:
            return JSONResponse(status_code=401, content={"detail": "Vui lòng đăng nhập Google."})
        if request.app.state.settings.invite_required and not account.trial_admitted:
            return JSONResponse(status_code=403, content={"detail": "Tài khoản chưa được mời dùng thử."})
        if account.role == "admin" and account.trial_admitted:
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        if account.root_department_id is None:
            return JSONResponse(status_code=403, content={"detail": "Tài khoản đang chờ quản trị viên gán tỉnh/cơ quan."})
        root_id = str(account.root_department_id)
        if any(value != root_id for value in request.query_params.getlist("root_department_id")):
            return JSONResponse(status_code=403, content={"detail": "Tài khoản không được truy cập chi tiết tỉnh khác."})
        if path.startswith("/api/v1/national-summaries"):
            return JSONResponse(status_code=403, content={"detail": "Sử dụng bảng so sánh điểm tỉnh thay cho dữ liệu tổng hợp thô."})
        request.state.authorized_root_id = account.root_department_id
        request.state.authorized_account_id = account.id
        if account.access_tier == "agency":
            if account.unit_department_id is None:
                return JSONResponse(status_code=403, content={"detail": "Tài khoản chưa được gán cơ quan."})
            request.state.authorized_unit_id = account.unit_department_id
        if catalog_path:
            from qd766.province_roots import load_province_roots
            code=path.split("/")[-2]
            if not any(root.province_code==code and root.root_department_id==account.root_department_id for root in load_province_roots().values()):
                return JSONResponse(status_code=403,content={"detail":"Danh mục không thuộc tỉnh được gán."})
        if private_selection:
            try:
                from qd766.periods import PeriodSelection
                kind=request.query_params["period_type"];year=int(request.query_params["year"])
                value=int(request.query_params["period_value"]) if request.query_params.get("period_value") else None
                PeriodSelection(kind,year,value).validate_collectable()
                formality_id=uuid.UUID(request.query_params["formality_id"])
            except (KeyError,ValueError):return JSONResponse(status_code=422,content={"detail":"Lựa chọn TTHC không hợp lệ."})
            with request.app.state.session_factory() as db:
                statement=select(PaidDataRequest.id).where(PaidDataRequest.account_id==account.id,
                    PaidDataRequest.root_department_id==account.root_department_id,PaidDataRequest.formality_id==formality_id,
                    PaidDataRequest.period_type==kind,PaidDataRequest.year==year,PaidDataRequest.state=="ready")
                statement=statement.where(PaidDataRequest.period_value.is_(None) if value is None else PaidDataRequest.period_value==value)
                if db.scalar(statement.limit(1)) is None:
                    return JSONResponse(status_code=403,content={"detail":"Tài khoản chưa khai thác TTHC trong kỳ này. Hãy tạo yêu cầu lấy dữ liệu."})
    response = await call_next(request)
    if request.app.state.settings.require_login:
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
