"""Mocked provider only: retries must not leak secrets or multiply paid runs."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from qd766.backend.gemini_client import generate


class GeminiRetryTest(unittest.TestCase):
    def setUp(self):
        self.settings=SimpleNamespace(gemini_api_key='private-test-key',gemini_model='test-model')
        self.evidence={'findings':[{'id':'gap','title':'Test'}]}
        self.good={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({
            'recommendations':[{'findingId':'gap','action':'Rà soát hồ sơ và phân công xử lý.'}]
        })}]}}]}

    def run_provider(self,statuses,payload=None):
        requests=[]
        def respond(request):
            requests.append(request)
            status=statuses[min(len(requests)-1,len(statuses)-1)]
            return httpx.Response(status,json=(payload or self.good) if status==200 else {'error':'private-body'})
        client=httpx.Client(transport=httpx.MockTransport(respond))
        with patch('qd766.backend.gemini_client.httpx.Client',return_value=client), \
                patch('qd766.backend.gemini_client.time.sleep') as sleep:
            try:
                result=generate(self.settings,self.evidence)
            except Exception as error:
                result=error
        return result,requests,[call.args[0] for call in sleep.call_args_list]

    def test_success_after_two_503s(self):
        with self.assertLogs('qd766.backend.gemini_client',level='WARNING') as logs:
            result,requests,delays=self.run_provider([503,503,200])
        self.assertEqual(result[0]['id'],'gap')
        self.assertEqual(len(requests),3);self.assertEqual(delays,[2,4])
        self.assertEqual(len({r.content for r in requests}),1)
        self.assertTrue(all(r.headers['x-goog-api-key']=='private-test-key' for r in requests))
        self.assertNotIn('private-test-key',str(logs.output))
        self.assertNotIn('private-body',str(logs.output))

    def test_exhaustion_stops_after_three(self):
        result,requests,delays=self.run_provider([503])
        self.assertIsInstance(result,httpx.HTTPStatusError)
        self.assertEqual(len(requests),3);self.assertEqual(delays,[2,4])

    def test_other_errors_are_not_retried(self):
        for status in (400,401,403,404,429,500,502,504):
            with self.subTest(status=status):
                result,requests,delays=self.run_provider([status])
                self.assertIsInstance(result,httpx.HTTPStatusError)
                self.assertEqual(len(requests),1);self.assertEqual(delays,[])

    def test_invalid_output_is_not_retried(self):
        result,requests,delays=self.run_provider([200],{'candidates':[]})
        self.assertIsInstance(result,IndexError)
        self.assertEqual(len(requests),1);self.assertEqual(delays,[])

    def test_ambiguous_timeout_is_not_retried(self):
        def respond(request):
            raise httpx.ReadTimeout('private error',request=request)
        client=httpx.Client(transport=httpx.MockTransport(respond))
        with patch('qd766.backend.gemini_client.httpx.Client',return_value=client), \
                patch('qd766.backend.gemini_client.time.sleep') as sleep:
            with self.assertRaises(httpx.ReadTimeout):generate(self.settings,self.evidence)
            sleep.assert_not_called()


if __name__=='__main__':unittest.main()
