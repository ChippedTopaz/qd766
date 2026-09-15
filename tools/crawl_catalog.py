#!/usr/bin/env python3
"""Crawl the DVCQG evaluation dataset province by province."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Response, sync_playwright

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


def province_short_name(name: str) -> str:
    value = normal_name(name)
    value = re.sub(r"^UBND\s+", "", value, flags=re.I)
    value = re.sub(r"^Thành phố\s+", "", value, flags=re.I)
    value = re.sub(r"\btỉnh\b\s*", "", value, flags=re.I)
    return value.strip()


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
            "provinceShortName": province_short_name(name),
        })

    provinces.sort(key=lambda x: x["departmentCode"])
    dedup: dict[str, dict[str, Any]] = {}
    for row in provinces:
        dedup.setdefault(row["departmentCode"], row)
    return list(dedup.values())


def safe_preview(text: str, limit: int = 300) -> str:
    return text[:limit].replace("\r", " ").replace("\n", " ")


def parse_response(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("API response body is empty")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("API response is not a JSON object")
    if not isinstance(payload.get("data"), dict):
        raise ValueError("API response missing object field data")
    return payload


def response_matches_province(text: str, province: dict[str, Any]) -> bool:
    """Return True only when the service-results response is for the target province."""
    try:
        payload = parse_response(text)
    except Exception:
        return False
    overview = payload.get("data", {}).get("overview") or {}
    code = normal_name(overview.get("departmentCode"))
    name = normal_name(overview.get("departmentName"))
    expected_code = province["departmentCode"]
    expected_name = province["departmentName"]
    # Code is the strongest signal. For older/variant responses where overview
    # omits code, require an exact name match instead. Never accept Cả nước.
    if code:
        return code == expected_code
    return bool(name and name == expected_name and name != "Cả nước")


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


def visible_text_candidates(page) -> list[dict[str, Any]]:
    return page.evaluate(
        """
        () => {
          const out = [];
          const els = Array.from(document.querySelectorAll('button,[role="button"],[role="option"],li,span,div'));
          for (const el of els) {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            if (!r.width || !r.height || s.display === 'none' || s.visibility === 'hidden') continue;
            const text = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
            if (text && text.length <= 120) out.push({tag: el.tagName, text});
          }
          return out.slice(0, 2000);
        }
        """
    )


def click_province_in_ui(page, province: dict[str, Any]) -> bool:
    short_name = province["provinceShortName"]
    full_name = province["departmentName"]

    selectors = [
        page.get_by_role("button", name=re.compile(r"Tỉnh,? Thành phố", re.I)).first,
        page.get_by_text(re.compile(r"^Tỉnh,? Thành phố$", re.I)).first,
    ]
    opened = False
    for locator in selectors:
        try:
            if locator.count() and locator.is_visible():
                locator.click(timeout=2500)
                page.wait_for_timeout(500)
                opened = True
                break
        except Exception:
            pass

    if not opened:
        try:
            locator = page.locator('button,[role="button"]').filter(has_text=re.compile(r"Tỉnh|Thành phố|Địa phương", re.I)).first
            if locator.count() and locator.is_visible():
                locator.click(timeout=2500)
                page.wait_for_timeout(500)
                opened = True
        except Exception:
            pass

    if not opened:
        return False

    page.wait_for_timeout(300)

    names = [full_name, short_name]
    names.extend([
        re.sub(r"^UBND\s+", "", full_name, flags=re.I),
        re.sub(r"^UBND\s+(tỉnh|Thành phố)\s+", "", full_name, flags=re.I),
    ])

    for name in names:
        candidate = normal_name(name)
        if not candidate:
            continue
        locators = [
            page.get_by_role("option", name=re.compile(f"^{re.escape(candidate)}$", re.I)).first,
            page.get_by_text(re.compile(f"^{re.escape(candidate)}$", re.I)).last,
        ]
        for locator in locators:
            try:
                if locator.count() and locator.is_visible():
                    locator.click(timeout=2500)
                    page.wait_for_timeout(250)
                    return True
            except Exception:
                pass

    visible = visible_text_candidates(page)
    candidates = []
    for item in visible:
        text = normal_name(item.get("text"))
        if text.lower() in {short_name.lower(), full_name.lower()}:
            candidates.append(text)
        elif short_name and short_name.lower() in text.lower() and len(text) <= len(short_name) + 20:
            candidates.append(text)
    for text in sorted(set(candidates), key=len):
        try:
            loc = page.get_by_text(text, exact=True).last
            if loc.count() and loc.is_visible():
                loc.click(timeout=2500)
                page.wait_for_timeout(250)
                return True
        except Exception:
            pass
    return False


def capture_service_results_after_ui_selection(page, province: dict[str, Any], timeout_ms: int) -> tuple[int, str, str] | None:
    """Select province and accept only the matching service-results response.

    The page can emit a national response (overview=\"Cả nước\") while the
    selector is opening or changing. Never mistake that response for the target.
    """
    captured: dict[str, Any] = {}
    ignored_national = {"count": 0}

    def on_response(response: Response) -> None:
        if ENDPOINT not in response.url:
            return
        try:
            text = response.text()
        except Exception:
            return
        if not text.lstrip().startswith(("{", "[")):
            return
        if response_matches_province(text, province):
            captured["status"] = response.status
            captured["text"] = text
            captured["content_type"] = response.headers.get("content-type", "")
            return
        try:
            payload = parse_response(text)
            overview = payload.get("data", {}).get("overview") or {}
            if normal_name(overview.get("departmentName")) == "Cả nước":
                ignored_national["count"] += 1
        except Exception:
            pass

    page.on("response", on_response)
    try:
        if not click_province_in_ui(page, province):
            print("    UI province selection could not be completed")
            return None
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            if captured.get("text"):
                return int(captured["status"]), str(captured["text"]), str(captured.get("content_type", ""))
            page.wait_for_timeout(250)
        if ignored_national["count"]:
            print(f"    UI emitted {ignored_national['count']} national response(s); target response was not observed")
        return None
    finally:
        try:
            page.remove_listener("response", on_response)
        except Exception:
            pass


def request_json_via_browser(page, payload: dict[str, Any], timeout_ms: int) -> tuple[int, str, str]:
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


def crawl_with_browser_request(page, province: dict[str, Any], year: int, timeout_ms: int) -> tuple[int, str, str]:
    payload = {
        "timeType": "year",
        "year": year,
        "rootDepartmentId": province["departmentId"],
    }
    return request_json_via_browser(page, payload, timeout_ms)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=datetime.now().year)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--province-code", help="Crawl one province by code, e.g. H20")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout", type=int, default=45_000)
    parser.add_argument("--delay", type=float, default=2.5)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--ui-first", action="store_true", default=False,
                        help="Prefer real UI selection before direct browser fetch")
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
            page.wait_for_timeout(5000)
        except PlaywrightTimeoutError:
            print("Page navigation timed out; continuing.", file=sys.stderr)
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
                status = 200
                content_type = "application/json"
                print("    raw exists; using existing response (use --force to recrawl)")
            else:
                result = None

                if args.ui_first or args.all:
                    try:
                        result = capture_service_results_after_ui_selection(page, province, timeout_ms=args.timeout)
                        if result:
                            print("    captured matching service-results response from live DVCQG UI")
                    except Exception as exc:
                        print(f"    UI selection attempt failed: {exc}", file=sys.stderr)

                if result is None:
                    try:
                        status, text, content_type = crawl_with_browser_request(page, province, args.year, args.timeout)
                        result = (status, text, content_type)
                    except Exception as exc:
                        print(f"    browser fetch failed: {exc}", file=sys.stderr)

                if result is None:
                    manifest.append({
                        **province,
                        "rootDepartmentId": root_id,
                        "status": "request_failed",
                    })
                    print("    FAILED request; continuing to next province", file=sys.stderr)
                    time.sleep(args.delay)
                    continue

                status, text, content_type = result
                print(f"    HTTP {status} | content-type={content_type or '(none)'}")
                if status not in (200, 201):
                    print("    FAILED HTTP status; continuing to next province", file=sys.stderr)
                    manifest.append({
                        **province,
                        "rootDepartmentId": root_id,
                        "status": "http_error",
                        "httpStatus": status,
                        "responseSha256": sha256_text(text),
                        "bodyPreview": safe_preview(text),
                    })
                    time.sleep(args.delay)
                    continue

                if not text.lstrip().startswith(("{", "[")):
                    print(f"    FAILED non-JSON body: {safe_preview(text)!r}", file=sys.stderr)
                    manifest.append({
                        **province,
                        "rootDepartmentId": root_id,
                        "status": "non_json",
                        "httpStatus": status,
                        "contentType": content_type,
                        "responseSha256": sha256_text(text),
                        "bodyPreview": safe_preview(text),
                    })
                    time.sleep(args.delay)
                    continue

                raw_path.write_text(text, encoding="utf-8")

            try:
                response_payload = parse_response(text)
                province_record, province_agencies, province_communes, warnings = verify_and_extract(
                    province, response_payload
                )
            except Exception as exc:
                print(f"    FAILED verification: {exc}", file=sys.stderr)
                print(f"    BODY PREVIEW: {safe_preview(text)!r}", file=sys.stderr)
                manifest.append({
                    **province,
                    "rootDepartmentId": root_id,
                    "status": "verification_error",
                    "error": str(exc),
                    "bodyPreview": safe_preview(text),
                    "responseSha256": sha256_text(text),
                })
                time.sleep(args.delay)
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
