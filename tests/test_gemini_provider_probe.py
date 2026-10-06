import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import httpx

spec=importlib.util.spec_from_file_location('probe',Path(__file__).resolve().parents[1]/'tools/check_gemini_provider.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


class ProbeTest(unittest.TestCase):
    def test_no_call_without_explicit_confirmation(self):
        with patch.object(probe,'probe') as call,patch.object(probe,'read_config') as read,redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main([]),0);call.assert_not_called();read.assert_not_called()

    def test_single_small_request_and_sanitized_error(self):
        calls=[]
        def respond(request):
            calls.append(request)
            return httpx.Response(503,json={'error':{'status':'UNAVAILABLE','message':'high demand private-key'}})
        client=httpx.Client(transport=httpx.MockTransport(respond));output=io.StringIO()
        with patch.object(probe.httpx,'Client',return_value=client),redirect_stdout(output):
            self.assertEqual(probe.probe({'QD766_GEMINI_MODEL':'test-model','QD766_GEMINI_API_KEY':'private-key'}),1)
        self.assertEqual(len(calls),1)
        self.assertIn('PROVIDER_STATUS=UNAVAILABLE',output.getvalue())
        self.assertIn('REASON=PROVIDER_HIGH_DEMAND',output.getvalue())
        self.assertNotIn('private-key',output.getvalue())

    def test_200_needs_actual_text(self):
        for text,expected in [('OK',0),('',1)]:
            client=httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,
                json={'candidates':[{'content':{'parts':[{'text':text}]}}]})))
            with patch.object(probe.httpx,'Client',return_value=client),redirect_stdout(io.StringIO()):
                self.assertEqual(probe.probe({'QD766_GEMINI_MODEL':'test-model','QD766_GEMINI_API_KEY':'private-key'}),expected)


if __name__=='__main__':unittest.main()
