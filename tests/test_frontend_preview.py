"""Preview is loopback-only and operation reads do not grant mutation rights."""
import importlib.util
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "frontend_preview", Path(__file__).resolve().parents[1] / "tools/preview_frontend.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


class FrontendPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = preview.http.server.ThreadingHTTPServer(("127.0.0.1", 0), preview.Preview)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_operation_reads_are_explicitly_allowlisted(self):
        paths = {"/api/v1/system-status", "/api/v1/collection-jobs",
                 "/api/v1/formality-batches", "/api/v1/province-batches"}
        self.assertTrue(paths <= preview.ALLOWED)
        self.assertNotIn("/api/v1/collection-control", preview.ALLOWED)
        self.assertNotIn("/api/v1/auth/me", preview.ALLOWED)

    def test_writes_and_unapproved_reads_never_reach_backend(self):
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with patch.object(preview.urllib.request, "build_opener") as backend:
            for method, path in [("POST", "/api/v1/province-batches"),
                                 ("POST", "/api/v1/collection-control"),
                                 ("GET", "/api/v1/collection-control")]:
                request = urllib.request.Request(self.url + path, method=method)
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    opener.open(request)
                self.assertEqual(caught.exception.code, 403)
                caught.exception.close()
            backend.assert_not_called()
