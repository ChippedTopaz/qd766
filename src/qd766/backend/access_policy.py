"""Fail-closed public preview boundary; not a replacement for account authentication."""
from fastapi import Request
from starlette.responses import JSONResponse

PUBLIC_READ_PATHS = frozenset({
    "/api/v1/access-policy", "/api/v1/health/live", "/api/v1/health/ready",
    "/api/v1/dashboard", "/api/v1/dashboard/selection",
    "/api/v1/dashboard/provinces", "/api/v1/dashboard/province-rankings",
    "/api/v1/national-summaries", "/api/v1/national-summaries/latest",
})


async def enforce_public_read_only(request: Request, call_next):
    if not request.app.state.settings.public_read_only:
        return await call_next(request)
    path = request.url.path.rstrip("/") or "/"
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
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
