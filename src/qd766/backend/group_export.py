"""Read-only, allowlisted data for the six-group workbook. Never collect or debit."""
from copy import deepcopy
from fastapi import HTTPException
from .dashboard import GROUP_LABELS


def group_export_payload(snapshot, *, unit_id=None, selected_group="all"):
    if selected_group != "all" and selected_group not in GROUP_LABELS:
        raise HTTPException(422, "Nhóm chỉ tiêu không hợp lệ.")
    if snapshot.get("delivery", {}).get("detailsAvailable") is False:
        raise HTTPException(409, "Kỳ này mới có điểm tổng hợp tỉnh, chưa có dữ liệu chi tiết cơ quan để xuất biểu.")
    groups = []
    units = {}
    # The unit allowlist is determined by the authenticated server-side account,
    # not by the browser's selected unit or a hidden worksheet.
    for dataset in snapshot.get("datasets", []):
        entities = [dataset.get("root", {}), *dataset.get("children", [])]
        allowed = [item for item in entities if item.get("departmentId") and
                   (unit_id is None or item["departmentId"] == str(unit_id))]
        for item in allowed:
            units.setdefault(item["departmentId"], {
                key: item.get(key) for key in ("departmentId", "departmentName", "departmentLevel")})
        if selected_group not in ("all", dataset["group"]):
            continue
        rows = []
        for item in allowed:
            row = {key: deepcopy(item.get(key)) for key in (
                "departmentId", "apiScore", "apiMaxScore", "apiRatio", "scoreSource", "parameters")}
            row["metrics"] = [{key: deepcopy(metric.get(key)) for key in (
                "code", "name", "numerator", "denominator", "ratio", "apiScore", "apiMaxScore")}
                for metric in item.get("metrics", []) if metric.get("code") != "scoreDelta"]
            row["parameters"] = {key: value for key, value in (row["parameters"] or {}).items()
                                 if key != "scoreDelta" and isinstance(value, (int, float, str, bool, type(None)))}
            rows.append(row)
        groups.append({"id": dataset["group"], "label": GROUP_LABELS[dataset["group"]],
                       "capturedAt": dataset.get("capture", {}).get("capturedAt"), "entities": rows})
    if not units:
        raise HTTPException(404, "Chưa có dữ liệu chi tiết của cơ quan được phân quyền trong kỳ này.")
    if selected_group == "all":
        existing = {group["id"] for group in groups}
        groups.extend({"id": key, "label": label, "capturedAt": None, "entities": []}
                      for key, label in GROUP_LABELS.items() if key not in existing)
    elif not groups:
        groups.append({"id": selected_group, "label": GROUP_LABELS[selected_group],
                       "capturedAt": None, "entities": []})
    return {"units": list(units.values()), "groups": groups,
            "delivery": deepcopy(snapshot.get("delivery", {})),
            "accessScope": "agency" if unit_id is not None else "province"}
