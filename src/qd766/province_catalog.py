from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


INDEX_URL = (
    "https://raw.githubusercontent.com/ChippedTopaz/am-sieu-toc-data/data/index.json"
)
VERSION_URL = (
    "https://raw.githubusercontent.com/ChippedTopaz/am-sieu-toc-data/data/version.json"
)
RULES_URL = (
    "https://raw.githubusercontent.com/ChippedTopaz/am-sieu-toc-data/niemyet/isVertical.json"
)

# Administrative codes used by the source application after the 2025 merger.
PROVINCES: dict[str, tuple[str, str]] = {
    "01": ("Hà Nội", "ha-noi"),
    "04": ("Cao Bằng", "cao-bang"),
    "08": ("Tuyên Quang", "tuyen-quang"),
    "11": ("Điện Biên", "dien-bien"),
    "12": ("Lai Châu", "lai-chau"),
    "14": ("Sơn La", "son-la"),
    "15": ("Lào Cai", "lao-cai"),
    "19": ("Thái Nguyên", "thai-nguyen"),
    "20": ("Lạng Sơn", "lang-son"),
    "22": ("Quảng Ninh", "quang-ninh"),
    "24": ("Bắc Ninh", "bac-ninh"),
    "25": ("Phú Thọ", "phu-tho"),
    "31": ("Hải Phòng", "hai-phong"),
    "33": ("Hưng Yên", "hung-yen"),
    "37": ("Ninh Bình", "ninh-binh"),
    "38": ("Thanh Hóa", "thanh-hoa"),
    "40": ("Nghệ An", "nghe-an"),
    "42": ("Hà Tĩnh", "ha-tinh"),
    "44": ("Quảng Trị", "quang-tri"),
    "46": ("Huế", "hue"),
    "48": ("Đà Nẵng", "da-nang"),
    "51": ("Quảng Ngãi", "quang-ngai"),
    "52": ("Gia Lai", "gia-lai"),
    "56": ("Khánh Hòa", "khanh-hoa"),
    "66": ("Đắk Lắk", "dak-lak"),
    "68": ("Lâm Đồng", "lam-dong"),
    "75": ("Đồng Nai", "dong-nai"),
    "79": ("Thành phố Hồ Chí Minh", "ho-chi-minh"),
    "80": ("Tây Ninh", "tay-ninh"),
    "82": ("Đồng Tháp", "dong-thap"),
    "86": ("Vĩnh Long", "vinh-long"),
    "91": ("An Giang", "an-giang"),
    "92": ("Cần Thơ", "can-tho"),
    "96": ("Cà Mau", "ca-mau"),
}


class ProvinceCatalogError(RuntimeError):
    pass


class ProvinceCatalogUnavailable(ProvinceCatalogError):
    pass


class ProvinceCatalogFormatError(ProvinceCatalogError):
    pass


@dataclass(frozen=True)
class Province:
    code: str
    name: str
    slug: str


@dataclass(frozen=True)
class ProvinceFormality:
    id: str
    code: str
    name: str
    field: str
    publishing_agency: str
    execution_levels: tuple[str, ...]
    formality_type: str
    state: str
    is_vertical: bool


@dataclass(frozen=True)
class ProvinceCatalog:
    province: Province
    master_updated_at: str
    rules_sha256: str
    include_internal: bool
    formalities: tuple[ProvinceFormality, ...]

    def select(
        self,
        level: str | None = None,
        field: str | None = None,
        query: str | None = None,
    ) -> tuple[ProvinceFormality, ...]:
        normalized_query = _plain(query).strip()
        return tuple(
            item
            for item in self.formalities
            if (level is None or level in item.execution_levels)
            and (field is None or item.field == field)
            and (
                not normalized_query
                or normalized_query in _plain(item.code)
                or normalized_query in _plain(item.name)
            )
        )

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(sorted({item.field for item in self.formalities if item.field}))

    @property
    def total_count(self) -> int:
        return len(self.formalities)

    @property
    def province_count(self) -> int:
        return len(self.select("province"))

    @property
    def ward_count(self) -> int:
        return len(self.select("ward"))


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    return "".join(character for character in text if unicodedata.category(character) != "Mn").replace("đ", "d")


def _lower(value: object) -> str:
    return str(value or "").lower()


def _code_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if not isinstance(item, dict)]


def _domain_matches(field: str, publisher: str, rules: object) -> bool:
    if not isinstance(rules, list):
        return False
    return any(
        isinstance(rule, dict)
        and str(rule.get("linh_vuc") or "").lower() in field
        and str(rule.get("co_quan_cong_bo") or "").lower() in publisher
        for rule in rules
    )


class AmSieuTocCatalogClient:
    def __init__(
        self,
        index_url: str = INDEX_URL,
        version_url: str = VERSION_URL,
        rules_url: str = RULES_URL,
        *,
        timeout_seconds: float = 30.0,
        fetch_json: Callable[[str], object] | None = None,
    ) -> None:
        self.index_url = index_url
        self.version_url = version_url
        self.rules_url = rules_url
        self.timeout_seconds = timeout_seconds
        self.fetch_json = fetch_json or self._fetch_json

    def _fetch_json(self, url: str) -> object:
        request = Request(url, headers={"User-Agent": "QD766/0.2 catalog-reader"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise ProvinceCatalogUnavailable(str(error)) from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ProvinceCatalogFormatError(str(error)) from error

    def load(self, province_code: str, *, include_internal: bool = True) -> ProvinceCatalog:
        if province_code not in PROVINCES:
            raise ProvinceCatalogFormatError("unknown province code")
        index = self.fetch_json(self.index_url)
        version = self.fetch_json(self.version_url)
        rules = self.fetch_json(self.rules_url)
        if not isinstance(index, list) or not isinstance(version, dict) or not isinstance(rules, dict):
            raise ProvinceCatalogFormatError("unexpected source document shape")
        updated_at = version.get("last_updated")
        if not isinstance(updated_at, str):
            raise ProvinceCatalogFormatError("version.last_updated is missing")

        rule_payload = json.dumps(
            rules, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        name, slug = PROVINCES[province_code]
        province = Province(province_code, name, slug)
        selected = self._filter(index, rules, province, include_internal)
        return ProvinceCatalog(
            province=province,
            master_updated_at=updated_at,
            rules_sha256=hashlib.sha256(rule_payload).hexdigest(),
            include_internal=include_internal,
            formalities=tuple(sorted(selected, key=lambda item: item.code)),
        )

    @staticmethod
    def _filter(
        index: list[object],
        rules: dict,
        province: Province,
        include_internal: bool,
    ) -> list[ProvinceFormality]:
        whitelist_codes = set(_code_list(rules.get("whitelist_codes")))
        whitelist_domains = rules.get("whitelist_domains")
        banned_codes = set(_code_list(rules.get("banned_codes")))
        banned_domains = rules.get("banned_domains")
        province_name = _plain(province.name).replace("tinh ", "").replace("thanh pho ", "")
        result: list[ProvinceFormality] = []

        for raw in index:
            if not isinstance(raw, dict):
                continue
            formality_type = str(raw.get("loai_tthc") or raw.get("formalityType") or "")
            if not include_internal and "nội bộ" in formality_type.lower():
                continue

            code = str(raw.get("ma_tthc") or raw.get("code") or "")
            field = str(raw.get("linh_vuc") or raw.get("field") or "")
            publisher = str(raw.get("co_quan_cong_bo") or raw.get("publishingAgency") or "")
            levels_text = _lower(raw.get("cap_thuc_hien") or raw.get("executionLevel"))
            province_level = (
                "tỉnh" in levels_text
                or "thành phố trực thuộc" in levels_text
                or raw.get("isProvince") is True
            )
            ward_level = (
                "xã" in levels_text
                or "phường" in levels_text
                or raw.get("isWard") is True
            )
            if not (province_level or ward_level):
                continue

            field_lower = field.lower()
            publisher_lower = publisher.lower()
            vertical = raw.get("nganh_doc") is True or _lower(raw.get("nganh_doc")) == "true"
            whitelisted = code in whitelist_codes or _domain_matches(
                field_lower, publisher_lower, whitelist_domains
            )
            if whitelisted:
                vertical = False
            elif code in banned_codes or _domain_matches(
                field_lower, publisher_lower, banned_domains
            ):
                vertical = True

            publisher_plain = _plain(publisher)
            current_province = province_name in publisher_plain
            other_province = not current_province and any(
                marker in publisher_plain
                for marker in ("ubnd", "uy ban nhan dan", "tinh ", "thanh pho ")
            )
            ministry = not current_province and not other_province
            if other_province or not ((ministry and not vertical) or current_province):
                continue

            levels = tuple(
                level
                for level, enabled in (("province", province_level), ("ward", ward_level))
                if enabled
            )
            result.append(
                ProvinceFormality(
                    id=str(raw.get("id") or ""),
                    code=code,
                    name=str(raw.get("ten_tthc") or raw.get("name") or ""),
                    field=field,
                    publishing_agency=publisher,
                    execution_levels=levels,
                    formality_type=formality_type,
                    state=str(raw.get("state") or ""),
                    is_vertical=vertical,
                )
            )
        return result
