from __future__ import annotations

import json
import os
import unicodedata
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from qd766.province_catalog import PROVINCES


DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "config" / "provinces.json"
)


@dataclass(frozen=True)
class ProvinceRoot:
    province_code: str
    province_name: str
    root_department_id: uuid.UUID
    department_name: str
    department_code: str
    source: str


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "").casefold())
    text = "".join(
        character
        for character in text
        if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")
    for prefix in ("ubnd thanh pho ", "ubnd tinh ", "thanh pho ", "tinh "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return " ".join(text.split())


def catalog_path() -> Path:
    configured = os.environ.get("QD766_PROVINCE_ROOTS_PATH")
    return Path(configured).expanduser() if configured else DEFAULT_CATALOG_PATH


@lru_cache(maxsize=1)
def load_province_roots() -> dict[str, ProvinceRoot]:
    """Load verified DVCQG root identities and map them to application codes."""
    path = catalog_path()
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("provinces")
    if not isinstance(rows, list):
        raise ValueError(f"Invalid province root catalog: {path}")

    application_codes = {
        _plain(province_name): (province_code, province_name)
        for province_code, (province_name, _) in PROVINCES.items()
    }
    roots: dict[str, ProvinceRoot] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        department_name = str(row.get("departmentName") or "").strip()
        matched = application_codes.get(_plain(department_name))
        if matched is None:
            continue
        province_code, province_name = matched
        roots[province_code] = ProvinceRoot(
            province_code=province_code,
            province_name=province_name,
            root_department_id=uuid.UUID(str(row["rootDepartmentId"])),
            department_name=department_name,
            department_code=str(row.get("departmentCode") or "").strip(),
            source=str(row.get("sourceUrl") or payload.get("source") or "").strip(),
        )

    if len(roots) != len(PROVINCES):
        missing = sorted(set(PROVINCES) - set(roots))
        raise ValueError(
            f"Province root catalog maps {len(roots)}/{len(PROVINCES)} provinces; "
            f"missing application codes: {', '.join(missing)}"
        )
    return roots


def province_root(province_code: str | None) -> ProvinceRoot | None:
    if province_code is None:
        return None
    return load_province_roots().get(province_code)
