"""Compress analytics responses, never authentication or invitation responses."""
from starlette.middleware.gzip import GZipMiddleware


class DashboardGZipMiddleware:
    def __init__(self, app):
        self.app = app
        self.compressed = GZipMiddleware(app, minimum_size=1024, compresslevel=1)

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if (scope["type"] == "http" and scope.get("method") == "GET"
                and (path == "/api/v1/dashboard" or path.startswith("/api/v1/dashboard/"))):
            await self.compressed(scope, receive, send)
        else:
            await self.app(scope, receive, send)
