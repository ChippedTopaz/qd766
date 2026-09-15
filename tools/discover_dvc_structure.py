#!/usr/bin/env python3
"""
Discover the DVCQG evaluation data structure from the live website.

This is a discovery tool, NOT the production crawler yet.
It uses a real Chromium session to observe the public evaluation page and its
JSON/XHR traffic, then builds a local catalog of:

  - province/root department records
  - AGENCY records (so/nganh)
  - COMMUNE records (xa/phuong/dac khu)
  - raw service-results responses observed during discovery
  - an audit trail showing where each record was found

Important:
  * Never invent a UUID.
  * Keep departmentId, departmentName and departmentCode exactly as observed.
  * childGroup is treated as a structural dimension: AGENCY or COMMUNE.
  * The production collector will later use rootDepartmentId to request each
    province. This tool only discovers and verifies the structure first.

Outputs:
  data/config/provinces.json
  data/config/departments.json
  data/discovery/<timestamp>/network-responses/*.json
  data/discovery/<timestamp>/audit.json

Usage:
  pip install -r tools/requirements.txt
  playwright install chromium
  python tools/discover_dvc_structure.py
  python tools/discover_dvc_structure.py --headed

Notes:
  The DVCQG page can lazy-load data. A headed run is useful during initial
  discovery so that the operator can change the province selector manually.
  The script also attempts conservative automatic interaction with selects and
  buttons that look like province selectors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Response, TimeoutError as PlaywrightTimeoutError, sync_playwright

DEFAULT_URL = "https://dichvucong.gov.vn/danh-gia-chat-luong-phuc-vu"
DEFAULT_ENDPOINT_FRAGMENT = "/api/v1/reporting/evaluation/service-results"
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONFIG_DIR = DATA_DIR / "config"
DISCOVERY_DIR = DATA_DIR / "discovery"

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

# The current 34-province/municipality set is intentionally NOT hard-coded here.
# Province membership is inferred from the actual service-results response.
# If the site exposes a lookup catalog, it will be captured as evidence too.
PROVINCE_NAME_RE = re.compile(r"(?:^|\s)(?:UBND\s+)?(?:tỉnh|thành phố)\s+(.+)$", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_uuid(value: Any) -> bool:
    return isinstance(value, str) and bool(UUID_RE.fullmatch(value.strip()))


def clean_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split()).strip()
    return value or None


def looks_like_department_record(obj: dict[str, Any]) -> bool:
    did = obj.get("departmentId")
    name = clean_string(obj.get("departmentName"))
    code = clean_string(obj.get("departmentCode"))
    return is_uuid(did) and bool(name) and bool(code)


def walk(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            out.extend(walk(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            out.extend(walk(child, f"{path}[{index}]"))
    return out


def unwrap_service_results(payload: Any) -> dict[str, Any] | None:
    """Return the actual API data object when the response is service-results."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    return data if isinstance(data, dict) else None


def response_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def extract_department_records(payload: Any, source_url: str) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    service_data = unwrap_service_results(payload)

    targets: list[tuple[str, Any]] = []
    if service_data is not None:
        evaluation = service_data.get("evaluation")
        if isinstance(evaluation, list):
            targets.append(("$.data.evaluation", evaluation))
        overview = service_data.get("overview")
        if isinstance(overview, dict):
            targets.append(("$.data.overview", overview))

    # Also scan the whole payload for possible lookup/catalog records. The
    # exact DVCQG UI can change; broad discovery is safer than one CSS/JSON path.
    targets.extend(walk(payload))

    for path, node in targets:
        if not isinstance(node, dict) or not looks_like_department_record(node):
            continue
        record = {
            "departmentId": node["departmentId"],
            "departmentName": clean_string(node["departmentName"]),
            "departmentCode": clean_string(node["departmentCode"]),
            "childGroup": clean_string(node.get("childGroup")),
            "totalScore": node.get("totalScore"),
            "ratio": node.get("ratio"),
            "scoreDelta": node.get("scoreDelta"),
            "sourceUrl": source_url,
            "evidencePath": path,
        }
        records[record["departmentId"]] = record

    return list(records.values())


def infer_province_record(payload: Any) -> dict[str, Any] | None:
    """Infer the province itself from overview/evaluation without guessing IDs."""
    if not isinstance(payload, dict):
        return None
    data = unwrap_service_results(payload)
    if not data:
        return None

    overview = data.get("overview") if isinstance(data.get("overview"), dict) else {}
    name = clean_string(overview.get("departmentName"))
    code = clean_string(overview.get("departmentCode"))

    # Overview normally has name/code but may omit the UUID. Find the matching
    # province item in evaluation by departmentCode/name.
    evaluation = data.get("evaluation")
    if not isinstance(evaluation, list):
        return None

    candidates = [
        x for x in evaluation
        if isinstance(x, dict)
        and is_uuid(x.get("departmentId"))
        and clean_string(x.get("departmentName"))
        and clean_string(x.get("departmentCode"))
        and (
            (name and clean_string(x.get("departmentName")) == name)
            or (code and clean_string(x.get("departmentCode")) == code)
        )
    ]
    if not candidates:
        # Fall back only when the evaluation has a very clear province-looking
        # root record. Do NOT classify ordinary agency/commune rows as province.
        for x in evaluation:
            if not isinstance(x, dict):
                continue
            if x.get("childGroup") in ("AGENCY", "COMMUNE"):
                continue
            n = clean_string(x.get("departmentName"))
            if n and PROVINCE_NAME_RE.search(n) and is_uuid(x.get("departmentId")):
                candidates.append(x)
    if not candidates:
        return None

    row = candidates[0]
    return {
        "departmentId": row.get("departmentId"),
        "departmentName": clean_string(row.get("departmentName")) or name,
        "departmentCode": clean_string(row.get("departmentCode")) or code,
        "rootDepartmentId": None,
        "source": "service-results",
    }


def detect_request_root_id(response: Response) -> tuple[str | None, dict[str, Any] | None]:
    """Try to recover rootDepartmentId from the captured POST request payload."""
    try:
        if response.request.method.upper() != "POST":
            return None, None
        post_data = response.request.post_data
        if not post_data:
            return None, None
        request_json = json.loads(post_data)
        rid = request_json.get("rootDepartmentId") if isinstance(request_json, dict) else None
        if is_uuid(rid):
            return rid, request_json
    except Exception:
        pass
    return None, None


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def attempt_selector_interaction(page) -> dict[str, Any]:
    """Collect simple DOM clues and try safe interactions that may lazy-load catalogs."""
    info: dict[str, Any] = {"selects": [], "buttons": [], "clicks": []}

    try:
        selects = page.locator("select")
        for i in range(min(selects.count(), 20)):
            s = selects.nth(i)
            options = s.locator("option")
            values = []
            for j in range(min(options.count(), 100)):
                o = options.nth(j)
                values.append({"text": o.inner_text().strip(), "value": o.get_attribute("value")})
            info["selects"].append({"index": i, "options": values})
    except Exception:
        pass

    # Capture visible button/combobox labels as evidence; don't blindly click
    # arbitrary elements because the page may contain submit/navigation actions.
    try:
        buttons = page.locator("button, [role='button'], [role='combobox']")
        for i in range(min(buttons.count(), 80)):
            b = buttons.nth(i)
            try:
                if not b.is_visible():
                    continue
                text = " ".join((b.inner_text() or "").split())
                aria = b.get_attribute("aria-label") or ""
                title = b.get_attribute("title") or ""
                label = " ".join(x for x in (text, aria, title) if x).strip()
                if label:
                    info["buttons"].append({"index": i, "label": label[:200]})
            except Exception:
                continue
    except Exception:
        pass

    # Try native selects first. This is deterministic and low risk.
    for i in range(len(info["selects"])):
        try:
            s = page.locator("select").nth(i)
            current = (s.input_value() or "").strip()
            if current:
                continue
            opts = info["selects"][i]["options"]
            usable = [o for o in opts if o.get("value") and o.get("text") and "chọn" not in o["text"].lower()]
            if usable:
                s.select_option(usable[0]["value"])
                info["clicks"].append({"type": "select", "index": i, "value": usable[0]["value"], "text": usable[0]["text"]})
                page.wait_for_timeout(1500)
        except Exception:
            pass

    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true", help="Show Chromium window")
    parser.add_argument("--observation-seconds", type=int, default=15)
    parser.add_argument("--post-load-seconds", type=int, default=8)
    parser.add_argument("--endpoint-fragment", default=DEFAULT_ENDPOINT_FRAGMENT)
    parser.add_argument("--keep-all-json", action="store_true", help="Save every JSON response, not only service-results")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = DISCOVERY_DIR / timestamp
    network_dir = run_dir / "network-responses"
    network_dir.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    all_departments: dict[str, dict[str, Any]] = {}
    provinces: dict[str, dict[str, Any]] = {}
    observed_requests: list[dict[str, Any]] = []
    saved_files: list[str] = []
    dom_info: dict[str, Any] = {}
    seq = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        context = browser.new_context(locale="vi-VN", viewport={"width": 1440, "height": 1000})
        page = context.new_page()

        def on_response(response: Response) -> None:
            nonlocal seq
            try:
                ctype = (response.headers.get("content-type") or "").lower()
                url = response.url
                looks_json = "json" in ctype or "/api/" in url
                if not looks_json:
                    return
                try:
                    payload = response.json()
                except Exception:
                    text = response.text()
                    if not text.lstrip().startswith(("{", "[")):
                        return
                    payload = json.loads(text)

                root_id, request_json = detect_request_root_id(response)
                records = extract_department_records(payload, url)
                is_service = args.endpoint_fragment in url

                observed = {
                    "url": url,
                    "status": response.status,
                    "method": response.request.method,
                    "isServiceResults": is_service,
                    "requestRootDepartmentId": root_id,
                    "requestJson": request_json,
                    "responseSha256": response_hash(payload),
                    "departmentRecordCount": len(records),
                }
                observed_requests.append(observed)

                if args.keep_all_json or is_service:
                    seq += 1
                    file_path = network_dir / f"{seq:04d}.json"
                    save_json(file_path, {
                        "capturedAt": utc_now(),
                        "url": url,
                        "status": response.status,
                        "request": request_json,
                        "response": payload,
                    })
                    saved_files.append(str(file_path.relative_to(ROOT)))

                if not records:
                    return

                for row in records:
                    did = row["departmentId"]
                    existing = all_departments.get(did)
                    if existing is None:
                        all_departments[did] = row
                    else:
                        # Preserve the first stable identity, but fill missing
                        # optional values from later observations.
                        for key, value in row.items():
                            if existing.get(key) in (None, "") and value not in (None, ""):
                                existing[key] = value

                province = infer_province_record(payload)
                if province:
                    if root_id:
                        province["rootDepartmentId"] = root_id
                    key = province.get("departmentCode") or province.get("departmentId")
                    if key:
                        existing = provinces.get(key, {})
                        existing.update({k: v for k, v in province.items() if v not in (None, "")})
                        provinces[key] = existing

            except Exception as exc:
                observed_requests.append({"url": response.url, "error": str(exc)})

        page.on("response", on_response)

        print(f"Opening: {args.url}")
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=60_000)
        except PlaywrightTimeoutError:
            print("Initial navigation timed out; continuing with captured traffic.", file=sys.stderr)
        except Exception as exc:
            print(f"Navigation error: {exc}", file=sys.stderr)

        page.wait_for_timeout(args.post_load_seconds * 1000)
        dom_info = attempt_selector_interaction(page)
        page.wait_for_timeout(args.observation_seconds * 1000)

        if args.headed:
            print("Headed discovery complete. You may inspect the browser/network traffic manually.")
        browser.close()

    # Split departments by explicit childGroup. Root/province records have no
    # childGroup in the observed service-results structure.
    agencies = []
    communes = []
    unclassified = []
    for row in all_departments.values():
        group = (row.get("childGroup") or "").upper()
        if group == "AGENCY":
            agencies.append(row)
        elif group == "COMMUNE":
            communes.append(row)
        else:
            unclassified.append(row)

    provinces_list = sorted(provinces.values(), key=lambda x: (x.get("departmentCode") or "", x.get("departmentName") or ""))
    agencies.sort(key=lambda x: (x.get("departmentCode") or "", x.get("departmentName") or ""))
    communes.sort(key=lambda x: (x.get("departmentCode") or "", x.get("departmentName") or ""))
    unclassified.sort(key=lambda x: (x.get("departmentCode") or "", x.get("departmentName") or ""))

    provinces_output = {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "source": args.url,
        "count": len(provinces_list),
        "provinces": provinces_list,
        "note": "Province records are derived only from observed DVCQG responses. rootDepartmentId is populated only when it was present in the captured request payload.",
    }
    departments_output = {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "source": args.url,
        "summary": {
            "total": len(all_departments),
            "agency": len(agencies),
            "commune": len(communes),
            "unclassified": len(unclassified),
        },
        "agencies": agencies,
        "communes": communes,
        "unclassified": unclassified,
    }
    audit = {
        "schemaVersion": 1,
        "generatedAt": utc_now(),
        "source": args.url,
        "endpointFragment": args.endpoint_fragment,
        "summary": {
            "provinces": len(provinces_list),
            "departments": len(all_departments),
            "agency": len(agencies),
            "commune": len(communes),
            "unclassified": len(unclassified),
            "observedResponses": len(observed_requests),
        },
        "dom": dom_info,
        "observedRequests": observed_requests,
        "savedResponseFiles": saved_files,
        "warning": "This discovery run does not claim that all 34 provinces were discovered unless the captured data actually contains them. Missing provinces must be resolved by additional navigation/API discovery, not guessed UUIDs.",
    }

    save_json(CONFIG_DIR / "provinces.json", provinces_output)
    save_json(CONFIG_DIR / "departments.json", departments_output)
    save_json(run_dir / "audit.json", audit)

    print(json.dumps({
        "provinces": len(provinces_list),
        "departments": len(all_departments),
        "agency": len(agencies),
        "commune": len(communes),
        "unclassified": len(unclassified),
        "runDir": str(run_dir),
        "provincesFile": str(CONFIG_DIR / "provinces.json"),
        "departmentsFile": str(CONFIG_DIR / "departments.json"),
    }, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
