"""Reduce a shared cached dashboard copy, never mutate the cache itself."""
from copy import deepcopy


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
