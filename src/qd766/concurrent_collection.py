"""Bounded HTTP concurrency with per-group immutable capture checkpoints."""
from __future__ import annotations
import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx
from .collection import (CollectionError, SafetyStop, TransportFailure, TransportResponse,
                         _validate_response, _manifest_template, _write_json)
from .normalization import METRIC_GROUPS

class PooledHttpTransport:
    def __init__(self, *, max_workers=3, spacing=0.4, guard: Callable[[], None] | None=None):
        if not 1 <= max_workers <= 5 or spacing < 0:
            raise ValueError('Invalid concurrency or pacing')
        self.client=httpx.Client(timeout=httpx.Timeout(45,connect=10),
            limits=httpx.Limits(max_connections=max_workers,max_keepalive_connections=max_workers),
            headers={'Accept':'application/json','User-Agent':'qd766-research/1.0 (+controlled concurrency)'})
        self.lock=threading.Lock()
        self.next_start=0.0
        self.spacing=spacing
        self.guard=guard

    def post_json(self,url,payload):
        with self.lock:
            if self.guard:
                self.guard()
            time.sleep(max(0,self.next_start-time.monotonic()))
            self.next_start=time.monotonic()+self.spacing
        try:
            response=self.client.post(url,json=payload)
        except httpx.TransportError as exc:
            raise TransportFailure(type(exc).__name__) from exc
        return TransportResponse(response.status_code,response.content,response.headers.get('content-type'))

    def close(self):
        self.client.close()

def collect_concurrent_snapshot(plan, *, period, output_dir: Path, transport,
                                max_workers=3, max_retries=4, sleeper=time.sleep):
    if not plan or not 1 <= max_workers <= 5 or not 0 <= max_retries <= 5:
        raise ValueError('Invalid plan or concurrency')
    output_dir.mkdir(parents=True,exist_ok=True)
    path=output_dir/'manifest.json'
    scope='formality' if any('formalityId' in r.payload or 'formalityID' in r.payload for r in plan) else 'all'
    wanted=_manifest_template(plan,period,scope)
    manifest=json.loads(path.read_text(encoding='utf-8')) if path.exists() else wanted
    if any(manifest.get(k)!=wanted[k] for k in ('period','scope','expectedGroups')):
        raise CollectionError('Checkpoint identity differs from plan')
    captures={c['group']:c for c in manifest['captures']}
    pending=[]
    for request in plan:
        capture=captures.get(request.group)
        if capture:
            if capture['payload']!=request.payload or capture['url']!=request.url:
                raise CollectionError('Checkpoint request identity differs')
            raw=output_dir/capture['file']
            if not raw.is_file() or hashlib.sha256(raw.read_bytes()).hexdigest()!=capture['sha256']:
                raise CollectionError('Checkpoint missing or corrupt')
        else:
            pending.append(request)
    if not pending:
        manifest['status']='complete'
        _write_json(path,manifest)
        return manifest
    manifest.update(status='collecting',failure=None)
    manifest['groupFailures']={}
    _write_json(path,manifest)
    stopped=threading.Event()

    def fetch_page(request,payload):
        for attempt in range(max_retries+1):
            if stopped.is_set():
                raise CollectionError('Stopped before request')
            try:
                response=transport.post_json(request.url,payload)
            except TransportFailure:
                if attempt==max_retries:
                    raise
                sleeper(2**attempt)
                continue
            rejection=response.body[:4096].lower()
            if response.status in (401,403,429) or 'text/html' in (response.contentType or '').lower() or b'request rejected' in rejection or b'access denied' in rejection:
                stopped.set()
                raise SafetyStop(f'Source stop signal HTTP {response.status} for {request.group}')
            if response.status>=500 and attempt<max_retries:
                sleeper(2**attempt)
                continue
            if response.status not in (200,201):
                raise CollectionError(f'HTTP {response.status} for {request.group}')
            # Every page uses the same root and schema checks.
            _validate_response(request,response)
            return response
        raise CollectionError('Request retries exhausted')

    def fetch_group(request):
        first=fetch_page(request,request.payload)
        envelope=json.loads(first.body)
        data=envelope['data']
        key='evaluation' if request.group in METRIC_GROUPS else 'children'
        pagination=data.get('pagination') or {}
        pages=int(pagination.get('totalPages') or 1)
        if not 1 <= pages <= 100:
            raise CollectionError('Unexpected page count')
        ids={r['departmentId'] for r in data[key]}
        if len(ids)!=len(data[key]):
            raise CollectionError('Duplicate child identity')
        for page in range(2,pages+1):
            payload=dict(request.payload,currentPage=page)
            response=fetch_page(request,payload)
            page_data=json.loads(response.body)['data']
            for row in page_data[key]:
                if row['departmentId'] in ids:
                    raise CollectionError('Duplicate child across pages')
                ids.add(row['departmentId'])
                data[key].append(row)
            (output_dir/f'{request.group}.page-{page}.json').write_bytes(response.body)
        body=first.body
        if pages>1:
            (output_dir/f'{request.group}.page-1.json').write_bytes(first.body)
            data['collectionPagination']={'fetchedPages':pages,'assembled':True}
            body=json.dumps(envelope,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        destination=output_dir/request.outputFile
        temporary=destination.with_suffix(destination.suffix+'.tmp')
        temporary.write_bytes(body)
        temporary.replace(destination)
        return {'group':request.group,'method':'POST','url':request.url,'payload':request.payload,
            'httpStatus':first.status,'contentType':first.contentType,
            'capturedAt':datetime.now(timezone.utc).isoformat(),'file':request.outputFile,
            'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
            'verification':'json-envelope-schema-and-root-verified','pages':pages}

    safety_error=None
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures={pool.submit(fetch_group,r):r for r in pending}
        for future in as_completed(futures):
            request=futures[future]
            try:
                capture=future.result()
                manifest['captures'].append(capture)
            except Exception as exc:
                manifest['groupFailures'][request.group]={'kind':type(exc).__name__,'message':str(exc)[:240]}
                if isinstance(exc,SafetyStop):
                    safety_error=exc
                    stopped.set()
            # Only the coordinator writes the manifest, atomically after each group.
            _write_json(path,manifest)
    manifest['status']='halted' if safety_error else 'failed' if manifest['groupFailures'] else 'complete'
    _write_json(path,manifest)
    if safety_error:
        raise safety_error
    if manifest['groupFailures']:
        raise CollectionError('One or more groups failed; successful checkpoints retained')
    return manifest
