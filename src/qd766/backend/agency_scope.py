"""Reduce a shared cached dashboard copy, never mutate the cache itself."""
from copy import deepcopy
import math


def comparison_points(entity, group):
    """Only score labels/maxima: never dossier counts, ratios or raw parameters."""
    def numeric(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    points = {}
    for metric in entity.get('metrics', []):
        if numeric(metric.get('apiScore')):
            maximum = metric.get('apiMaxScore')
            points['raw:' + metric['code']] = {'label': metric['name'], 'score': metric['apiScore'],
                'maximum': maximum if numeric(maximum) else None}
    if group == 'dvc-progress-tree':
        params = entity.get('parameters', {})
        received, on_time = params.get('totalReceived'), params.get('totalOnTime')
        overdue = params.get('totalOverdue')
        maximum = entity.get('apiMaxScore')
        if numeric(received) and numeric(on_time) and numeric(maximum):
            overdue = overdue if overdue is not None else max(0, received - on_time)
            if numeric(overdue) and received > 0 and on_time >= 0 and overdue >= 0 and received == on_time + overdue:
                points['progress:on-time'] = {'label': 'Tỷ lệ hồ sơ giải quyết đúng hạn',
                    'score': on_time / received * maximum, 'maximum': maximum}
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
        for dataset in item.get("datasets", []):
            dataset["raw"] = {"path": "", "sha256": ""}
            root = dataset.get("root", {})
            score_only(root)
            for key in ("apiScore", "apiMaxScore", "apiRatio"):
                root[key] = None
            for child in dataset.get("children", []):
                if child.get("departmentId") != unit_id:
                    child['comparisonPoints'] = comparison_points(child, dataset.get('group'))
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
