#!/usr/bin/env python3
"""
Discover DVCQG province rootDepartmentId values without hard-coding IDs.

The DVCQG evaluation page is a browser application. The safest first step is to
let a real Chromium session load the page and inspect its JSON/XHR traffic.
The tool captures JSON responses and recursively searches them for department
records, especially objects containing an ID/name pair or explicit
rootDepartmentId fields.

Outputs:
  data/config/provinces-discovered.json

Usage:
  pip install -r requirements.txt
  playwright install chromium
  python tools/discover_root_departments.py

Optional:
  python tools/discover_root_departments.py --url https://dichvucong.gov.vn/danh-gia-chat-luong-phuc-vu
  python tools/discover_root_departments.py --headed
  python tools/discover_root_departments.py --timeout 60

The script never invents IDs. Ambiguous records are written to the audit file
for manual review instead of being silently accepted.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Response, sync_playwright

DEFAULT_URL = "https://dichvucong.gov.vn/danh-gia-chat-luong-phuc-vu"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "config"
OUTPUT_FILE = OUTPUT_DIR / "provinces-discovered.json"
AUDIT_FILE = OUTPUT_DIR / "root-department-discovery-audit.json"

VN_PROVINCES = {
    "An Giang", "Bắc Ninh", "Cà Mau", "Cao Bằng", "Đà Nẵng", "Đắk Lắk",
    "Điện Biên", "Đồng Nai", "Đồng Tháp", "Gia Lai", "Hà Nội", "Hà Tĩnh",
    "Hải Phòng", "Hậu Giang", "Hòa Bình", "Hưng Yên", "Khánh Hòa", "Kiên Giang",
    "Lai Châu", "Lạng Sơn", "Lào Cai", "Nghệ An", "Ninh Bình", "Phú Thọ",
    "Quảng Ngãi", "Quảng Ninh", "Quảng Trị", "Sóc Trăng", "Sơn La", "Tây Ninh",
    "Thái Nguyên", "Thanh Hóa", "TP. Hồ Chí Minh", "Thừa Thiên Huế", "Tiền Giang",
    "Trà Vinh", "Tuyên Quang", "Vĩnh Long", "Vĩnh Phúc", "Yên Bái",
}

# The 2026 administrative reorganisation changed the province set. The tool does
# not require this list to be complete: it is only used as a weak name heuristic.
PROVINCE_HINTS = (
    "Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ",
    "An Giang", "Bắc Ninh", "Cà Mau", "Cao Bằng", "Đắk Lắk", "Điện Biên",
    "Đồng Nai", "Đồng Tháp", "Gia Lai", "Hà Tĩnh", "Hưng Yên", "Khánh Hòa",
    "Lai Châu", "Lạng Sơn", "Lào Cai", "Nghệ An", "Ninh Bình", "Phú Thọ",
    "Quảng Ngãi", "Quảng Ninh", "Quảng Trị", "Sơn La", "Tây Ninh",
    "Thái Nguyên", "Thanh Hóa", "Thừa Thiên Huế", "Tiền Giang", "Trà Vinh",
    "Tuyên Quang", "Vĩnh Long", "Vĩnh Phúc", "Yên Bái",
)


@dataclass
class Candidate:
    name: str
    rootDepartmentId: str
    source_url: str
    evidence_path: str
    score: int
    raw: dict[str, Any]


def looks_like_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        value.strip(),
    ))


def clean_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = " ".join(value.split()).strip()
    if not s or len(s) > 160:
        return None
    return s


def name_score(name: str) -> int:
    score = 0
    if any(hint.lower() in name.lower() for hint in PROVINCE_HINTS):
        score += 4
    if re.search(r"\b(tỉnh|thành phố|TP\.)\b", name, re.I):
        score += 2
    if name.lower().startswith(("ubnd ", "ủy ban nhân dân")):
        score -= 2
    if re.search(r"\b(xã|phường|đặc khu|thị trấn)\b", name, re.I):
        score -= 4
    return score


def iter_nodes(value: Any, path: str = "$", seen: set[int] | None = None) -> Iterable[tuple[str, Any]]:
    if seen is None:
        seen = set()
    if isinstance(value, (dict, list)):
        obj_id = id(value)
        if obj_id in seen:
            return
        seen.add(obj_id)
    yield path, value
    if isinstance(value, dict):
        for k, v in value.items():
            yield from iter_nodes(v, f"{path}.{k}", seen)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from iter_nodes(v, f"{path}[{i}]", seen)


def candidate_from_dict(obj: dict[str, Any], path: str, url: str) -> Candidate | None:
    # Strongest signal: an explicit rootDepartmentId field.
    for id_key in ("rootDepartmentId", "rootDepartmentID"):
        rid = obj.get(id_key)
        if looks_like_uuid(rid):
            name = clean_name(
                obj.get("departmentName")
                or obj.get("name")
                or obj.get("rootDepartmentName")
                or obj.get("label")
            )
            if name:
                return Candidate(name, rid, url, path, 100 + name_score(name), obj)

    # Common lookup response shape: {id, name, code, ...}.
    rid = obj.get("id") or obj.get("departmentId") or obj.get("uuid")
    name = clean_name(
        obj.get("name")
        or obj.get("departmentName")
        or obj.get("ten")
        or obj.get("label")
    )
    if looks_like_uuid(rid) and name:
        score = 30 + name_score(name)
        if any(k in obj for k in ("departmentCode", "code", "type", "departmentType")):
            score += 5
        return Candidate(name, rid, url, path, score, obj)
    return None


def extract_candidates(payload: Any, url: str) -> list[Candidate]:
    out: list[Candidate] = []
    for path, node in iter_nodes(payload):
        if isinstance(node, dict):
            c = candidate_from_dict(node, path, url)
            if c:
                out.append(c)
    return out


def parse_json_response(response: Response) -> tuple[str, Any | None]:
    try:
        ct = (response.headers.get("content-type") or "").lower()
        if "json" not in ct:
            text = response.text()
            if not text.lstrip().startswith(("{", "[")):
                return ct, None
            return ct, json.loads(text)
        return ct, response.json()
    except Exception:
        return "", None


def merge_candidate(existing: dict[str, Any], c: Candidate) -> None:
    # Preserve best evidence, but retain all source URLs for auditability.
    existing["sources"] = sorted(set(existing.get("sources", [])) | {c.source_url})
    if c.score > existing.get("score", -1):
        existing.update({
            "name": c.name,
            "rootDepartmentId": c.rootDepartmentId,
            "score": c.score,
            "evidencePath": c.evidence_path,
            "raw": c.raw,
        })


def wait_for_manual_browser(page, seconds: int) -> None:
    print(f"No strong department lookup found yet. Keeping browser open for {seconds}s...", file=sys.stderr)
    page.wait_for_timeout(seconds * 1000)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--headed", action="store_true", help="Show Chromium window")
    parser.add_argument("--timeout", type=int, default=45, help="Extra observation time after page load")
    parser.add_argument("--slowmo", type=int, default=0)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates: dict[str, dict[str, Any]] = {}
    observations: list[dict[str, Any]] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed, slow_mo=args.slowmo)
        context = browser.new_context(
            locale="vi-VN",
            viewport={"width": 1440, "height": 1000},
        )
        page = context.new_page()

        def on_response(response: Response) -> None:
            ctype, payload = parse_json_response(response)
            if payload is None:
                return
            url = response.url
            found = extract_candidates(payload, url)
            if not found:
                return
            observations.append({
                "url": url,
                "status": response.status,
                "candidateCount": len(found),
                "candidates": [asdict(c) for c in found[:100]],
            })
            for c in found:
                key = c.rootDepartmentId
                if key not in candidates:
                    candidates[key] = {
                        "name": c.name,
                        "rootDepartmentId": c.rootDepartmentId,
                        "score": c.score,
                        "evidencePath": c.evidence_path,
                        "sources": [c.source_url],
                        "raw": c.raw,
                    }
                else:
                    merge_candidate(candidates[key], c)

        page.on("response", on_response)

        print(f"Opening {args.url}")
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=60_000)
        except PlaywrightTimeoutError:
            print("Page load timed out; continuing with captured network data.", file=sys.stderr)
        except Exception as exc:
            print(f"Page navigation failed: {exc}", file=sys.stderr)

        page.wait_for_timeout(8_000)

        # Try to expose any province/department selector without relying on one
        # fragile CSS selector. This is deliberately conservative: click only
        # controls whose accessible name strongly suggests a province selector.
        labels = ["Tỉnh", "Thành phố", "Chọn tỉnh", "Chọn địa phương", "Địa phương"]
        for label in labels:
            try:
                locator = page.get_by_text(label, exact=True).first
                if locator.count() and locator.is_visible():
                    locator.click(timeout=1500)
                    page.wait_for_timeout(1500)
                    break
            except Exception:
                pass

        # A page may lazily request lookup data after interaction.
        page.wait_for_timeout(max(2, args.timeout) * 1000)
        if not candidates:
            wait_for_manual_browser(page, 5 if args.headed else 2)

        browser.close()

    # Keep only records with a province-like name. Ambiguous records remain in audit.
    accepted = []
    ambiguous = []
    for row in sorted(candidates.values(), key=lambda x: (-x["score"], x["name"])):
        if row["score"] >= 32:
            accepted.append({
                "name": row["name"],
                "rootDepartmentId": row["rootDepartmentId"],
                "score": row["score"],
                "evidencePath": row["evidencePath"],
                "sources": row["sources"],
            })
        else:
            ambiguous.append(row)

    result = {
        "version": 1,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sourceUrl": args.url,
        "countAccepted": len(accepted),
        "provinces": accepted,
        "note": "IDs are discovered from live browser network traffic; no rootDepartmentId is fabricated.",
    }
    audit = {
        "generatedAt": result["generatedAt"],
        "sourceUrl": args.url,
        "candidateCount": len(candidates),
        "accepted": accepted,
        "ambiguous": ambiguous,
        "observations": observations,
    }

    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    AUDIT_FILE.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "accepted": len(accepted),
        "ambiguous": len(ambiguous),
        "output": str(OUTPUT_FILE),
        "audit": str(AUDIT_FILE),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
