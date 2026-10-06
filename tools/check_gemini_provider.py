"""Explicit single small provider probe. No DB, wallet, source data or retries."""
import argparse
import re
import sys
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from qd766.backend.public_deployment import read_config

STATUSES={'UNAVAILABLE','RESOURCE_EXHAUSTED','PERMISSION_DENIED','UNAUTHENTICATED',
          'INVALID_ARGUMENT','NOT_FOUND','INTERNAL','DEADLINE_EXCEEDED','FAILED_PRECONDITION'}


def probe(config):
    model=config['QD766_GEMINI_MODEL']
    with httpx.Client(timeout=httpx.Timeout(30,connect=10),follow_redirects=False) as client:
        response=client.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            headers={'x-goog-api-key':config['QD766_GEMINI_API_KEY']},
            json={'contents':[{'role':'user','parts':[{'text':'Trả lời đúng một từ: OK'}]}],
                  'generationConfig':{'maxOutputTokens':256}})
    print('HTTP_STATUS='+str(response.status_code))
    try:body=response.json()
    except ValueError:
        print('RESPONSE_FORMAT=NON_JSON');return 1
    if not isinstance(body,dict):
        print('RESPONSE_FORMAT=INVALID');return 1
    if response.status_code!=200:
        error=body.get('error');error=error if isinstance(error,dict) else {}
        status=error.get('status')
        print('PROVIDER_STATUS='+(status if isinstance(status,str) and status in STATUSES else 'UNKNOWN'))
        # Only emit fixed classifications, never provider text/echoed secrets.
        message=error.get('message');message=message.lower() if isinstance(message,str) else ''
        if response.status_code==503 and any(word in message for word in ('overloaded','high demand')):
            print('REASON=PROVIDER_HIGH_DEMAND')
        return 1
    candidates=body.get('candidates',[])
    text=''
    if isinstance(candidates,list) and candidates and isinstance(candidates[0],dict):
        content=candidates[0].get('content',{})
        parts=content.get('parts',[]) if isinstance(content,dict) else []
        if isinstance(parts,list):
            text=''.join(p.get('text','') for p in parts if isinstance(p,dict)
                         and isinstance(p.get('text'),str) and not p.get('thought'))
    print('TEXT_OUTPUT_PRESENT='+str(bool(text.strip())))
    print('SMALL_PROMPT_OK='+str(text.strip()=='OK'))
    return 0 if text.strip()=='OK' else 1


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-provider-call',action='store_true',
                        help='Make exactly one real API call, which may consume quota/billing')
    args=parser.parse_args(argv)
    if not args.confirm_provider_call:
        print('NO_PROVIDER_CALL; add --confirm-provider-call for one real small request.');return 0
    try:
        config=read_config(ROOT/'.env.gemini')
        if (set(config)!={'QD766_GEMINI_API_KEY','QD766_GEMINI_MODEL'} or
                not config['QD766_GEMINI_API_KEY'] or config['QD766_GEMINI_API_KEY'].startswith('<') or
                not re.fullmatch(r'[a-zA-Z0-9._-]{1,120}',config['QD766_GEMINI_MODEL'])):
            print('GEMINI_CONFIG=INVALID');return 1
        return probe(config)
    except Exception as error:
        # Error messages and tracebacks can contain credentials; never print them.
        print('PROBE_FAILED_TYPE='+type(error).__name__);return 1


if __name__=='__main__':raise SystemExit(main())
