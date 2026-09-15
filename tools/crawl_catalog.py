#!/usr/bin/env python3
"""Build and verify the DVCQG province/agency/commune catalog."""

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
        raise FileNotFoundError(f"Missing {PROVINCE_DISCOVERY}. Run discover_dvc_structure.py first.")

    payload = json.loads(PROVINCE_DISCOVERY.read_text(encoding="utf-8"))
    rows = payload.get("unclassified", [])
    provinces: list[dict[str, Any]] = []

    for row in rows:
        code = normal_name(row.get("departmentCode"))
        name = normal_name(row.get("departmentName"))
        department_id = normal_name(row.get("departmentId"))
        child_group = row.get("childGroup")
        if not code or not name or not department_id or child_group is not None:
            continue
        if not code.startswith("H"):
            continue
        provinces.append({
            "departmentId": department_id,
            "departmentName": name,
            "departmentCode": code,
        })

    provinces.sort(key=lambda x: x["departmentCode"])
    dedup: dict[str, dict[str, Any]] = {}
    for row in provinces:
        dedup.setdefault(row["departmentCode"], row)
    return list(dedup.values())


def request_json_via_browser(page, payload: dict[str, Any], timeout_ms: int) -> tuple[int, str, str]:
    """POST from the actual DVCQG page context.

    This is preferred over Playwright's separate APIRequestContext because the
    live page has the exact browser origin, cookies and request environment used
    by the website itself.
    """
    result = page.evaluate(
        """
        async ({url, payload}) => {
          const res = await fetch(url, {
            method: 'POST',
            credentials: 'include',
            headers: {
              'Accept': 'application/json, text/plain, */*',
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
          });
          const text = await res.text();
          return {
            status: res.status,
            contentType: res.headers.get('content-type') || '',
            text
          };
        }
        """,
        {"url": ENDPOINT, "payload": payload},
    )
    return int(result["status"]), str(result.get("text", "")), str(result.get("contentType", ""))


def request_json_via_context(context, payload: dict[str, Any], timeout_ms: int) -> tuple[int, str, str]:
    """Fallback request using the browser-context API client."""
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
    return response.status, response.text(), response.headers.get("content-type", "")


def request_json(page, context, payload: dict[str, Any], timeout_ms: int, retries: int, delay: float) -> tuple[int, str, str]:
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            status, text, content_type = request_json_via_browser(page, payload, timeout_ms)

            if status in (200, 201):
                if text.lstrip().startswith(("{", "[")):
                    return status, text, content_type

                # Some responses can be unusual/empty in page.fetch. Fall back
                # to the context client before declaring failure.
                try:
                    print("    Browser fetch returned non-JSON body; trying context.request fallback...")
                    s2, t2, ct2 = request_json_via_context(context, payload, timeout_ms)
                    if s2 in (200, 201) and t2.lstrip().startswith(("{", "[")):
                        return s2, t2, ct2
                    status, text, content_type = s2, t2, ct2
                except Exception as fallback_exc:
                    last_error = fallback_exc

                preview = text[:300].replace("\r", " ").replace("\n", " ")
                if attempt >= retries:
                    raise RuntimeError(
                        f"HTTP {status} returned non-JSON response (content-type={content_type!r}, "
                        f"body-preview={preview!r})"
                    )

            retryable = status == 429 or 500 <= status <= 599
            if not retryable and status not in (200, 201):
                return status, text, content_type

            if attempt < retries:
                wait = delay * (2 ** attempt)
                print(f"    HTTP {status}; retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            return status, text, content_type
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                wait = delay * (2 ** attempt)
                print(f"    request error: {exc}; retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Request failed after retries: {exc}") from exc

    raise RuntimeError(str(last_error) if last_error else "Unknown request failure")


def parse_response(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("API response body is empty")
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

    if overview_code and overview_code != expected_code:
        raise ValueError(f"Province verification failed: requested {expected_code} but overview is {overview_code}")
    if overview_name and overview_name != expected_name:
        raise ValueError(f"Province verification failed: requested '{expected_name}' but overview is '{overview_name}'")

    province_records: list[dict[str, Any]] = []
    agencies: list[dict[str, Any]] = []
    communes: list[dict[str, Any]] = []
    warnings: list[str] = []

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
            province_records.append(record)
        else:
            warnings.append(
                f"Unclassified evaluation record: {item.get('departmentCode')} / "
                f"{item.get('departmentName')} / childGroup={child_group}"
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
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--province-code", help="Crawl one province by code, e.g. H20")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout", type=int, default=60_000)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--force", action="store_true")
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
                status, text, content_type = request_json(
                    page,
                    context,
                    payload,
                    timeout_ms=args.timeout,
                    retries=args.retries,
                    delay=args.delay,
                )
                print(f"    HTTP {status} | content-type={content_type or '(none)'}")
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
                preview = text[:300].replace("\r", " ").replace("\n", " ")
                print(f"    FAILED verification: {exc}", file=sys.stderr)
                print(f"    BODY PREVIEW: {preview!r}", file=sys.stderr)
                manifest.append({
                    **province,
                    "rootDepartmentId": root_id,
                    "status": "verification_error",
                    "error": str(exc),
                    "bodyPreview": preview,
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
