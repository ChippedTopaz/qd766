"""Isolated UI preview: static assets and allowlisted GETs to the existing backend.

No worker, migrations, environment loading or collection requests. Port 8767 is
left untouched. Stop this preview with Ctrl+C.
"""
import argparse
import http.server
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"/api/v1/access-policy", "/api/v1/dashboard",
           "/api/v1/dashboard/selection", "/api/v1/dashboard/provinces",
           "/api/v1/dashboard/province-rankings"}


class Preview(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            if path not in ALLOWED:
                self.send_error(403, "Preview only allows dashboard reads")
                return
            try:
                # Never inherit an outbound proxy for this loopback-only read.
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                with opener.open("http://127.0.0.1:8767" + self.path, timeout=20) as response:
                    body, status = response.read(), response.status
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except urllib.error.HTTPError as error:
                self.send_error(error.code, "Backend read failed")
            except urllib.error.URLError:
                self.send_error(502, "Local backend is unavailable")
            return
        super().do_GET()

    def do_POST(self):
        self.send_error(403, "Read-only preview")

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    print(f"READ_ONLY_PREVIEW=http://127.0.0.1:{args.port}/", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Preview).serve_forever()
