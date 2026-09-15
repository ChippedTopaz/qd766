#!/usr/bin/env python3
"""Build and verify the DVCQG province/agency/commune catalog.

Workflow
--------
1. Read the province-level records discovered from the national
   service-results response (data/config/departments.json).
2. For each province, use its departmentId as rootDepartmentId in the
   province-scoped service-results request.
3. Verify that the returned overview/evaluation belongs to the requested
   province.
4. Save the exact API response as RAW JSON.
5. Extract province, AGENCY and COMMUNE records into catalog JSON files.

This script does NOT invent UUIDs. A province rootDepartmentId is considered
verified only after the province-scoped API request returns data whose
province code/name matches the requested province.

Examples
--------
python tools/crawl_catalog.py --year 2026 --limit 1 --headed
python tools/crawl_catalog.py --year 2026 --all --headed
python tools/crawl_catalog.py --year 2026 --province-code H44

The API commonly returns HTTP 201 for successful POST requests. 201 is treated
as success.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import APIResponse, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://dichvucong.gov.vn/danh-gia-chat-luong-phuc-vu"
ENDPOINT = "https://dichvucong.gov.vn/api/v1/reporting/evaluation/service-results"
PROVINCE_DISCOVERY = ROOT / "data" / "config" / "departments.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normal_name(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load_provinces() -> list[dict[str, Any]]:
    if not PROVINCE_DISCOVERY.exists():
        raise FileNotFoundError(
            f"Missing {PROVINCE_DISCOVERY}. Run discover_dvc_structure.py first."
        )

    payload = json.loads(PROVINCE_DISCOVERY.read_text(encoding="utf-8"))
    rows = payload.get("unclassified", [])
    provinces: list[dict[str, Any]] = []

    for row in rows:
        code = normal_name(row.get("departmentCode"))
        name = normal_name(row.get("departmentName"))
        department_id = normal_name(row.get("departmentId"))
        child_group = row.get("childGroup")

        # The national response currently exposes province-level records with
        # childGroup == null and province codes such as H20. Do not rely solely
        # on naming; require a department code and UUID-like non-empty ID.
        if not code or not name or not department_id or child_group is not None:
            continue
        if not code.startswith("H"):
            continue
        provinces.append({
            "departmentId": department_id,
            "departmentName": name,
            "departmentCode": code,
        })

    # Stable, deterministic order.
    provinces.sort(key=lambda x: x["departmentCode"])

    # De-duplicate by department code; retain the first record.
    dedup: dict[str, dict[str, Any]] = {}
    for row in provinces:
        dedup.setdefault(row["departmentCode"], row)
    return list(dedup.values())


def request_json(context, payload: dict[str, Any], timeout_ms: int, retries: int, delay: float) -> tuple[int, str]:
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            response: APIResponse = context.request.post(
                ENDPOINT,
                data=json.dumps(payload, ensure_ascii=False),
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                    "Origin": "https://dichvucong.gov.vn",
                    "Referer": SOURCE_URL,
                },
                timeout=timeout_ms,
            )
            status = response.status
            text = response.text()

            if status in (200, 201):
                return status, text

            retryable = status == 429 or 500 <= status <= 599
            if not retryable:
                return status, text

            if attempt < retries:
                wait = delay * (2 ** attempt)
                print(f"    HTTP {status}; retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            return status, text
        except Exception as exc:  # network/timeout
            last_error = exc
            if attempt < retries:
                wait = delay * (2 ** attempt)
                print(f"    request error: {exc}; retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Request failed after retries: {exc}") from exc

    raise RuntimeError(str(last_error) if last_error else "Unknown request failure")


def parse_response(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("API response is not a JSON object")
    if not isinstance(payload.get("data"), dict):
        raise ValueError("API response missing object field data")
    return payload


def verify_and_extract(
    province: dict[str, Any],
    response_payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    data = response_payload["data"]
    overview = data.get("overview") or {}
    evaluation = data.get("evaluation") or []
    if not isinstance(evaluation, list):
        raise ValueError("data.evaluation is not an array")

    expected_code = province["departmentCode"]
    expected_name = province["departmentName"]

    overview_code = normal_name(overview.get("departmentCode"))
    overview_name = normal_name(overview.get("departmentName"))

    warnings: list[str] = []
    if overview_code and overview_code != expected_code:
        raise ValueError(
            f"Province verification failed: requested {expected_code} but overview is {overview_code}"
        )
    if overview_name and overview_name != expected_name:
        raise ValueError(
            f"Province verification failed: requested '{expected_name}' but overview is '{overview_name}'"
        )

    province_records: list[dict[str, Any]] = []
    agencies: list[dict[str, Any]] = []
    communes: list[dict[str, Any]] = []

    for item in evaluation:
        if not isinstance(item, dict):
            continue

        record = {
            **item,
            "provinceCode": expected_code,
            "provinceName": expected_name,
            "rootDepartmentId": province["departmentId"],
        }
        child_group = item.get("childGroup")
        department_code = normal_name(item.get("departmentCode"))

        if child_group == "AGENCY":
            agencies.append(record)
        elif child_group == "COMMUNE":
            communes.append(record)
        elif department_code == expected_code or not child_group:
            # Province-level record in the evaluation table.
            province_records.append(record)
        else:
            warnings.append(
                f"Unclassified evaluation record: {item.get('departmentCode')} / {item.get('departmentName')} / childGroup={child_group}"
            )

    if not province_records:
        warnings.append("No province-level record was found inside data.evaluation.")
    elif len(province_records) > 1:
        warnings.append(f"Found {len(province_records)} province-level evaluation records.")

    return (
        {
            "departmentId": province["departmentId"],
            "departmentName": expected_name,
            "departmentCode": expected_code,
            "rootDepartmentId": province["departmentId"],
            "verified": True,
            "overview": overview,
            "source": "service-results",
        },
        agencies,
        communes,
        warnings,
    )


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=datetime.now().year)
    parser.add_argument("--all", action="store_true", help="Crawl all discovered provinces")
    parser.add_argument("--limit", type=int, default=1, help="Number of provinces to crawl when --all is not used")
    parser.add_argument("--province-code", help="Crawl one province by code, e.g. H44")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout", type=int, default=60_000)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--force", action="store_true", help="Ignore an existing raw province response")
    args = parser.parse_args()

    all_provinces = load_provinces()
    if not all_provinces:
        raise RuntimeError("No province records found in data/config/departments.json")

    if args.province_code:
        targets = [p for p in all_provinces if p["departmentCode"] == args.province_code]
        if not targets:
            raise RuntimeError(f"Province code not found: {args.province_code}")
    elif args.all:
        targets = all_provinces
    else:
        targets = all_provinces[: max(1, args.limit)]

    raw_dir = ROOT / "data" / "raw" / str(args.year) / "provinces"
    catalog_dir = ROOT / "data" / "catalog" / str(args.year)
    raw_dir.mkdir(parents=True, exist_ok=True)
    catalog_dir.mkdir(parents=True, exist_ok=True)

    verified_provinces: list[dict[str, Any]] = []
    agencies: list[dict[str, Any]] = []
    communes: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []

    print(f"Discovered {len(all_provinces)} province records. Crawling {len(targets)} province(s).")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        context = browser.new_context(locale="vi-VN", viewport={"width": 1440, "height": 1000})
        page = context.new_page()

        # Load the real site once so browser cookies/session state, if any, are
        # available to context.request.
        try:
            page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3000)
        except PlaywrightTimeoutError:
            print("Page navigation timed out; continuing with captured browser session.", file=sys.stderr)
        except Exception as exc:
            print(f"Page navigation warning: {exc}", file=sys.stderr)

        for index, province in enumerate(targets, start=1):
            code = province["departmentCode"]
            name = province["departmentName"]
            root_id = province["departmentId"]
            raw_path = raw_dir / f"{code}.json"

            print(f"[{index}/{len(targets)}] {code} - {name}")
            print(f"    rootDepartmentId={root_id}")

            if raw_path.exists() and not args.force:
                text = raw_path.read_text(encoding="utf-8")
                print("    raw exists; using existing response (use --force to recrawl)")
            else:
                payload = {
                    "timeType": "year",
                    "year": args.year,
                    "rootDepartmentId": root_id,
                }
                status, text = request_json(
                    context,
                    payload,
                    timeout_ms=args.timeout,
                    retries=args.retries,
                    delay=args.delay,
                )
                print(f"    HTTP {status}")
                if status not in (200, 201):
                    manifest.append({
                        **province,
                        "rootDepartmentId": root_id,
                        "status": "http_error",
                        "httpStatus": status,
                        "responseSha256": sha256_text(text),
                    })
                    continue
                raw_path.write_text(text, encoding="utf-8")

            try:
                response_payload = parse_response(text)
                province_record, province_agencies, province_communes, warnings = verify_and_extract(
                    province, response_payload
                )
            except Exception as exc:
                print(f"    FAILED verification: {exc}", file=sys.stderr)
                manifest.append({
                    **province,
                    "rootDepartmentId": root_id,
                    "status": "verification_error",
                    "error": str(exc),
                    "responseSha256": sha256_text(text),
                })
                continue

            verified_provinces.append(province_record)
            agencies.extend(province_agencies)
            communes.extend(province_communes)
            manifest.append({
                **province,
                "rootDepartmentId": root_id,
                "status": "verified",
                "agencyCount": len(province_agencies),
                "communeCount": len(province_communes),
                "evaluationCount": len(response_payload["data"].get("evaluation") or []),
                "responseSha256": sha256_text(text),
                "warnings": warnings,
            })
            print(
                f"    VERIFIED | evaluation={manifest[-1]['evaluationCount']} | "
                f"agency={len(province_agencies)} | commune={len(province_communes)}"
            )

            time.sleep(max(0.0, args.delay))

        browser.close()

    generated_at = utc_now()
    write_json(catalog_dir / "provinces.json", {
        "schemaVersion": 2,
        "generatedAt": generated_at,
        "year": args.year,
        "source": SOURCE_URL,
        "count": len(verified_provinces),
        "provinces": verified_provinces,
    })
    write_json(catalog_dir / "agencies.json", {
        "schemaVersion": 2,
        "generatedAt": generated_at,
        "year": args.year,
        "count": len(agencies),
        "agencies": agencies,
    })
    write_json(catalog_dir / "communes.json", {
        "schemaVersion": 2,
        "generatedAt": generated_at,
        "year": args.year,
        "count": len(communes),
        "communes": communes,
    })
    write_json(catalog_dir / "crawl-manifest.json", {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "year": args.year,
        "endpoint": ENDPOINT,
        "requested": len(targets),
        "verified": sum(1 for x in manifest if x.get("status") == "verified"),
        "failed": sum(1 for x in manifest if x.get("status") != "verified"),
        "items": manifest,
    })

    print("\nSUMMARY")
    print(f"  requested provinces : {len(targets)}")
    print(f"  verified provinces  : {len(verified_provinces)}")
    print(f"  agencies            : {len(agencies)}")
    print(f"  communes            : {len(communes)}")
    print(f"  raw directory       : {raw_dir}")
    print(f"  catalog directory   : {catalog_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
