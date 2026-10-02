"""Fail-closed public preview boundary; not a replacement for account authentication."""
from fastapi import Request
from starlette.responses import JSONResponse
from .auth import current_session, SESSION_COOKIE

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
    if path in AUTH_READ_PATHS or path == "/api/v1/auth/logout":
        allowed = request.method == "GET" if path in AUTH_READ_PATHS else request.method == "POST"
        if not allowed:
            return JSONResponse(status_code=405, content={"detail": "Method not allowed"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    if not request.app.state.settings.public_read_only:
        return await call_next(request)
    allowed = request.method in {"GET", "HEAD"}
    if path.startswith("/api/"):
        allowed = allowed and path in PUBLIC_READ_PATHS
        allowed = allowed and all(value == "all" for value in request.query_params.getlist("scope"))
        allowed = allowed and not any(key.lower().replace("_", "") == "formalityid" for key in request.query_params)
    else:
        allowed = allowed and (path in {"/", "/index.html", "/styles.css"}
            or path.startswith("/dist/") and path.endswith(".js")
            or path.startswith("/vendor/") and path.endswith((".js", ".css")))
    if not allowed:
        return JSONResponse(status_code=403, content={"detail": "Chế độ dùng thử chỉ cho phép đọc dữ liệu tổng hợp. Tính năng này cần xác thực và phân quyền trước khi mở."})
    if request.app.state.settings.require_login and path.startswith("/api/") and path not in BOOTSTRAP_PATHS:
        with request.app.state.session_factory() as db:
            _, account = current_session(db, request.cookies.get(SESSION_COOKIE))
        if account is None:
            return JSONResponse(status_code=401, content={"detail": "Vui lòng đăng nhập Google."})
        if account.root_department_id is None:
            return JSONResponse(status_code=403, content={"detail": "Tài khoản đang chờ quản trị viên gán tỉnh/cơ quan."})
        root_id = str(account.root_department_id)
        if any(value != root_id for value in request.query_params.getlist("root_department_id")):
            return JSONResponse(status_code=403, content={"detail": "Tài khoản không được truy cập chi tiết tỉnh khác."})
        if path.startswith("/api/v1/national-summaries"):
            return JSONResponse(status_code=403, content={"detail": "Sử dụng bảng so sánh điểm tỉnh thay cho dữ liệu tổng hợp thô."})
        request.state.authorized_root_id = account.root_department_id
    response = await call_next(request)
    if request.app.state.settings.require_login:
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
