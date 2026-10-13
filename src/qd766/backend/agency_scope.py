"""Reduce a shared cached dashboard copy, never mutate the cache itself."""
from copy import deepcopy
import math


def comparison_points(entity, group, scope='all'):
    """Only score labels/maxima: never dossier counts, ratios or raw parameters."""
    def numeric(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    points = {}
    for metric in entity.get('metrics', []):
        if numeric(metric.get('apiScore')):
            maximum = metric.get('apiMaxScore')
            points['raw:' + metric['code']] = {'score': metric['apiScore'],
                'maximum': maximum if numeric(maximum) else None}
    if group == 'dvc-progress-tree':
        params = entity.get('parameters', {})
        received, on_time = params.get('totalReceived'), params.get('totalOnTime')
        overdue = params.get('totalOverdue')
        maximum = entity.get('apiMaxScore')
        if numeric(received) and numeric(on_time) and numeric(maximum):
            overdue = overdue if overdue is not None else max(0, received - on_time)
            if numeric(overdue) and received > 0 and on_time >= 0 and overdue >= 0 and received == on_time + overdue:
                points['progress:on-time'] = {'score': on_time / received * maximum, 'maximum': maximum}
    if group == 'formality-online-payment-tree':
        params = entity.get('parameters', {})
        definitions = [
            ('3.5','totalFeeDossierFormality','totalFeeFormality',2,80),
            ('3.5b','totalDossierOnlineFormalityPaymentSuccess','totalFeeDossierFormalityDistinct',2,80),
            ('3.6','totalDossierOnlinePaymentSuccess','totalDossierFinancialObligation',6,100),
        ]
        for code,numerator,denominator,maximum,target in definitions:
            if scope == 'formality' and code != '3.6':
                numerator,denominator = ('agencyPaymentProvidedNumerator','agencyPaymentProvidedDenominator') if code == '3.5' else ('agencyPaymentTransactionsNumerator','agencyPaymentTransactionsDenominator')
            a,b=params.get(numerator),params.get(denominator)
            if numeric(a) and numeric(b) and b>0 and 0<=a<=b:
                score=math.floor(min(maximum,a/b*100/target*maximum)*100+.5+1e-9)/100
                points['payment:'+code]={'score':score,'maximum':maximum}
    return points


def restrict_agency(payload: dict, unit_id) -> dict:
    if unit_id is None:
        return payload
    result = deepcopy(payload)
    unit_id = str(unit_id)

    def score_only(entity):
        entity["metrics"] = []
        entity["parameters"] = {}

    def snapshot(item):
        item["provinceAggregatedScore"] = None
        item["provinceAggregatedMaximum"] = None
        level = next((child.get('departmentLevel') for dataset in item.get('datasets', [])
            for child in dataset.get('children', []) if child.get('departmentId') == unit_id
            and child.get('departmentLevel') in {'COMMUNE', 'PROVINCE'}), None)
        progress=next((g for g in item.get('datasets',[]) if g.get('group')=='dvc-progress-tree'),{})
        own=next((e for e in progress.get('children',[]) if e.get('departmentId')==unit_id),{})
        volume=own.get('parameters',{}).get('totalReceived')
        def valid_volume(value):
            return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0
        if item.get('scope')=='all':
            for peer in progress.get('children',[]):
                received=peer.get('parameters',{}).get('totalReceived')
                peer['similarReceivedVolume']=(volume*.8<=received<=volume*1.2) if valid_volume(volume) and valid_volume(received) else None
        for dataset in item.get("datasets", []):
            dataset["raw"] = {"path": "", "sha256": ""}
            root = dataset.get("root", {})
            # Explicit same-province online reference only; never expose other groups,
            # other agencies' details, raw records, or purchased procedure datasets.
            if item.get('scope') == 'all' and dataset.get('group') == 'provide-online-tree':
                allowed = {'authorityCount','partialCount','fullCount','channelDirectSum',
                    'channelPostalSum','channelTotalSum','channelOnlineSum','onlineOnTimeSum',
                    'onlineOverdueSum','onlineDossierCount','onlineServiceTotal'}
                dataset['provinceOnlineParameters'] = {key: value for key, value in
                    root.get('parameters', {}).items() if key in allowed and
                    isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)}
            score_only(root)
            for key in ("apiScore", "apiMaxScore", "apiRatio"):
                root[key] = None
            for child in dataset.get("children", []):
                if child.get("departmentId") != unit_id:
                    child['comparisonPoints'] = comparison_points(child, dataset.get('group'), item.get('scope','all')) if (
                        level is not None and child.get('departmentLevel') == level) else {}
                    score_only(child)
    if "snapshots" in result:
        result["units"] = [unit for unit in result.get("units", []) if unit.get("departmentId") == unit_id]
        result["defaultUnitId"] = unit_id
        result["metricCatalog"] = []
        for item in result["snapshots"].values():
            snapshot(item)
    elif "snapshot" in result:
        snapshot(result["snapshot"])
    return result
