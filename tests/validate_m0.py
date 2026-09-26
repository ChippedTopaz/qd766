"""Offline validation of captured M0 evidence. Never calls DVCQG."""
import argparse
import hashlib
import json
from pathlib import Path

RID = '019d2be3-6a88-732b-8b17-b68020c8553a'
FID = '019d2bfd-8e22-77ef-819f-e49460350904'
GROUPS = {
    'transparency': (200, 'formalityId', {'PUBLISH_ON_TIME':6,'PUBLIC_UPDATE_ON_TIME':4,'PUBLIC_CONTENT_FULL':2,'DOSSIER_SYNC':6}),
    'handling-satisfaction': (200, None, {'PETITION_CLASSIFICATION_TTHC':0,'DOSSIER_RECEIVING_SATISFACTION':6,'PETITION_PROCESSING_ON_TIME':6,'PETITION_HANDLING_SATISFACTION':6,'PETITION_CLASSIFICATION_STAFF':0}),
    'dossier-digitized': (200, 'formalityID', {'ORIGINAL_RESULT_AVAILABLE':6,'SO_HOA_GIAY_TO_GIAI_QUYET':4,'REUSED_DIGITIZED_DATA':2,'SYNCED_WITH_DVCQG_PERSONAL_STORAGE':4,'CITIZEN_DATA_CONNECTED_DOSSIER':2,'CITIZEN_DATA_CONNECTED_FORMALITY':2,'ELECTRONIC_CERTIFIED_COPY':2}),
    'dvc-progress-tree': (100,'formalityId',None),
    'provide-online-tree': (200,'formalityId',None),
    'formality-online-payment-tree': (100,'formalityId',None),
}
PARAMETERS = {
    'dvc-progress-tree': ['totalReceived','totalOnTime','totalCompleted','avgProcessingDays'],
    'provide-online-tree': ['authorityCount','partialCount','fullCount','onlineDossierCount','onlineServiceTotal','channelOnlineSum','channelDirectSum','channelPostalSum','channelTotalSum','onlineOnTimeSum','onlineOverdueSum'],
    'formality-online-payment-tree': ['totalDossierOnlinePaymentSuccess','totalDossierFinancialObligation','totalDossierOnlineFormalityPaymentSuccess','totalFeeDossierFormalityDistinct','totalFeeDossierFormality','totalFeeFormality'],
}
def require(condition, message):
    if not condition: raise ValueError(message)
def read(path): return json.loads(path.read_bytes())
def validate(root):
    fix=root/'tests/fixtures'; manifest=read(fix/'manifest.m0.json')
    require(manifest.get('status')=='validated-offline','Manifest is not marked validated-offline')
    names=[x['file'] for x in manifest['captures']]
    expected={f'{g}/{p}-{s}.json' for g,(_,k,_) in GROUPS.items() for p in ['month','quarter','year'] for s in (['all','formality'] if k else ['all'])}
    expected|={f'formalities/{n}.json' for n in ['code-2.000815-page-1','page-1','page-2','page-last']}
    require(len(names)==len(set(names)) and set(names)==expected,'Missing, duplicate or unexpected manifest capture')
    loaded={}; warnings=[]
    for cap in manifest['captures']:
        name=cap['file']; raw=(fix/name).read_bytes(); obj=json.loads(raw); loaded[name]=obj
        require(hashlib.sha256(raw).hexdigest()==cap['sha256'] and len(raw)==cap['bytes'],f'{name}: raw bytes changed')
        require(cap['httpStatus'] in [200,201] and obj['code']=='OK',f'{name}: unsuccessful response')
        require(cap['method']=='POST' and bool(cap['capturedAt']),f'{name}: missing provenance')
        g=name.split('/')[0]; data=obj['data']; p=cap['payload']
        require(cap['url']=='https://dichvucong.gov.vn/api/v1/reporting/'+('formalities' if g=='formalities' else 'evaluation/'+g),f'{name}: wrong endpoint')
        if g=='formalities':
            require(set(p)<= {'q','currentPage','pageSize'},f'{name}: unexpected catalog payload')
            pg=data['pagination']; items=data['items']
            require(pg['currentPage']==p['currentPage'] and pg['pageSize']==p['pageSize'],f'{name}: pagination echo mismatch')
            require(pg['totalPages']==(pg['total']+pg['pageSize']-1)//pg['pageSize'],f'{name}: page count inconsistent')
            require(len(items)==min(pg['pageSize'],max(0,pg['total']-(pg['currentPage']-1)*pg['pageSize'])),f'{name}: item count inconsistent')
            for item in items:
                require(all(k in item for k in ['id','code','name','state','departmentId','publishingDepartmentIds','appliedDepartmentIds']),f'{name}: catalog item missing fields')
                require(isinstance(item['appliedDepartmentIds'],list) and all(isinstance(i,str) for i in item['appliedDepartmentIds']),f'{name}: invalid appliedDepartmentIds')
            continue
        size,key,codes=GROUPS[g]; period=cap['period']; scope=cap['scope']
        expected_payload={'rootDepartmentId':RID,'currentPage':1,'pageSize':size}
        if g=='handling-satisfaction':
            expected_payload.update(fromDate={'year':'2026-01-01','quarter':'2026-07-01','month':'2026-08-01'}[period],toDate={'year':'2026-12-31','quarter':'2026-09-30','month':'2026-08-31'}[period])
        else:
            expected_payload.update(timeType=period,year=2026)
            if period!='year':expected_payload[period]=8 if period=='month' else 3
        if scope=='formality': expected_payload[key]=FID
        require(p==expected_payload,f'{name}: payload mismatch including formality key casing')
        require(name==f'{g}/{period}-{scope}.json',f'{name}: scope label mismatch')
        parent=data['overview' if codes else 'parent']; children=data['evaluation' if codes else 'children']
        require(parent['departmentId']==RID and parent['departmentName']=='UBND tỉnh Phú Thọ',f'{name}: wrong province')
        require(isinstance(children,list) and len(children)>0,f'{name}: no child scope evidence')
        require(all(isinstance(c,dict) and isinstance(c.get('departmentId'),str) for c in children),f'{name}: child identity missing')
        if codes:
            metrics=parent['metrics']; actual_codes={m['code']:m['maxScore'] for m in metrics}
            if g=='dossier-digitized' and scope=='formality':
                # The live API omits this aggregate-only metric when one TTHC is selected.
                expected_codes={k:v for k,v in codes.items() if k!='CITIZEN_DATA_CONNECTED_FORMALITY'}
            else:
                expected_codes=codes
            require(actual_codes==expected_codes,f'{name}: metric definitions differ: {actual_codes}')
            for record in [parent,*children]:
                for m in record['metrics']:
                    require(all(k in m for k in ['code','name','numerator','denominator','ratio','score','maxScore']),f'{name}: metric fields missing')
                    require(all(m[k] is None or type(m[k]) in (int,float) for k in ['numerator','denominator','ratio','score','maxScore']),f'{name}: metric number/null type changed')
                    if m.get('dataQualityStatus'):warnings.append(m['dataQualityStatus'])
            pg=data['pagination']; require(pg['total']==len(children) and pg['totalPages']==1,f'{name}: incomplete evaluation page')
        else:
            require(all(k in parent for k in PARAMETERS[g]),f'{name}: missing business parameters')
            require('metrics' not in parent,f'{name}: unexpected metric-code schema')
    target=loaded['formalities/code-2.000815-page-1.json']['data']['items']
    require(len(target)==1 and target[0]['code']=='2.000815' and target[0]['id']==FID,'Wrong representative formality')
    require(len(target[0]['appliedDepartmentIds'])==3629,'Representative applied scope differs from captured contract')
    for group,(_,formality_key,_) in GROUPS.items():
        if not formality_key: continue
        for period in ['month','quarter','year']:
            all_raw=(fix/f'{group}/{period}-all.json').read_bytes()
            selected_raw=(fix/f'{group}/{period}-formality.json').read_bytes()
            require(all_raw!=selected_raw,f'{group}/{period}: TTHC fixture is identical to all-procedure fixture')
    pages=[loaded[f'formalities/{n}.json']['data'] for n in ['page-1','page-2','page-last']]
    require([p['pagination']['currentPage'] for p in pages]==[1,2,575],'Wrong pagination boundary fixtures')
    require(len({p['pagination']['total'] for p in pages})==1,'Catalog changed during capture')
    ids=[i['id'] for p in pages for i in p['items']]
    require(len(ids)==len(set(ids)),'Catalog page samples overlap')
    metrics=read(root/'docs/metrics.m0.json'); rows=metrics['rows']
    require(len(rows)==24 and sum(r['maxScore'] for r in rows if r['maxScore'] is not None)==100,'METRICS province maximum does not reconcile')
    for r in rows:
        g=r['apiUrl'].strip().rsplit('/',1)[-1]
        require(g in GROUPS,f"METRICS row {r['sourceRow']}: unmapped API URL")
        if r['metricCode']:
            require(r['metricCode'] in GROUPS[g][2],f"METRICS row {r['sourceRow']}: code missing in response")
            require(r['maxScore']==GROUPS[g][2][r['metricCode']],f"METRICS row {r['sourceRow']}: maximum differs")
    return {'result':'PASS','scope':'Offline captured-fixture integrity, payload and response contract only; not production or scoring correctness','captures':len(names),'evaluationFixtures':33,'catalogFixtures':4,'metricsRows':24,'declaredProvinceMaximum':100,'qualityFlags':sorted(set(warnings)),'remainingGaps':['Dịch vụ công trực tuyến chưa xác định được công thức; giả thuyết thành phần trước đây không ổn định trên fixture tháng 8','SYNCED_WITH_DVCQG_PERSONAL_STORAGE chưa có quan sát tỷ lệ dương','METRICS maxScore blank at STT 7,8,9,10,18','Live responses do not echo formality ID; filtering evidence combines deployed client source, selected UI, catalog identity and changed all/formality results','Unseen provinces, periods, empty catalogs and error responses are outside this M0 sample']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--report',type=Path);args=p.parse_args()
    try: result=validate(args.root)
    except Exception as e: result={'result':'FAIL','error':str(e)}
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.report:args.report.write_text(text+'\n',encoding='utf-8')
    print(text)
    raise SystemExit(0 if result['result']=='PASS' else 1)
