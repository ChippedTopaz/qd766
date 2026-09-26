"""Build complete normalized QĐ766 snapshots from captured datasets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from .normalization import ALL_GROUPS, NormalizedDataset, normalize_fixture
from .periods import PeriodSelection

FORMALITY_ID = "019d2bfd-8e22-77ef-819f-e49460350904"

GROUP_ORDER = [
    "transparency",
    "dvc-progress-tree",
    "provide-online-tree",
    "dossier-digitized",
    "handling-satisfaction",
    "formality-online-payment-tree",
]

UNSUPPORTED_BY_SCOPE = {
    "formality": {"handling-satisfaction"},
    "all": set(),
}


@dataclass
class SnapshotStatus:
    state: Literal["complete", "incomplete"]
    requiredGroups: list[str]
    loadedGroups: list[str]
    unsupportedGroups: list[str]
    missingGroups: list[str]


@dataclass
class NormalizedSnapshot:
    schemaVersion: int
    period: dict[str, Any]
    scope: str
    formalityId: str | None
    status: SnapshotStatus
    scorePolicy: dict[str, Any]
    provinceAggregatedScore: float | int | None
    provinceAggregatedMaximum: float | int | None
    datasets: list[NormalizedDataset]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def period_dict(period: PeriodSelection) -> dict[str, Any]:
    result: dict[str, Any] = {"type": period.type, "year": period.year}
    if period.value is not None:
        result[period.type] = period.value
    return result


def build_fixture_snapshot(
    fixtures_root: Path,
    period: PeriodSelection,
    scope: Literal["all", "formality"] = "all",
) -> NormalizedSnapshot:
    """Build an offline M1 snapshot from M0 fixtures.

    A formality snapshot is complete with five datasets because satisfaction is
    an explicitly unsupported group, rather than a failed or missing request.
    """

    if scope not in UNSUPPORTED_BY_SCOPE:
        raise ValueError(f"Unsupported scope: {scope}")
    unsupported = UNSUPPORTED_BY_SCOPE[scope]
    required = [group for group in GROUP_ORDER if group not in unsupported]
    normalized_period = period_dict(period)
    datasets: list[NormalizedDataset] = []
    missing: list[str] = []
    for group in required:
        path = fixtures_root / group / f"{period.type}-{scope}.json"
        if not path.exists():
            missing.append(group)
            continue
        datasets.append(
            normalize_fixture(
                path,
                fixtures_root=fixtures_root,
                group=group,
                period=normalized_period,
                scope=scope,
                formality_id=FORMALITY_ID if scope == "formality" else None,
            )
        )

    return _assemble_snapshot(
        normalized_period,
        scope,
        FORMALITY_ID if scope == "formality" else None,
        required,
        sorted(unsupported),
        missing,
        datasets,
    )


def _assemble_snapshot(
    normalized_period: dict[str, Any],
    scope: str,
    formality_id: str | None,
    required: list[str],
    unsupported: list[str],
    missing: list[str],
    datasets: list[NormalizedDataset],
) -> NormalizedSnapshot:
    scores = [dataset.root.apiScore for dataset in datasets]
    maxima = [dataset.root.apiMaxScore for dataset in datasets]
    can_total = not missing and all(value is not None for value in scores + maxima)
    status = SnapshotStatus(
        state="complete" if not missing else "incomplete",
        requiredGroups=required,
        loadedGroups=[dataset.group for dataset in datasets],
        unsupportedGroups=unsupported,
        missingGroups=missing,
    )
    return NormalizedSnapshot(
        schemaVersion=1,
        period=normalized_period,
        scope=scope,
        formalityId=formality_id,
        status=status,
        scorePolicy={
            "authoritativeValue": "apiScore",
            "aggregation": "sum root apiScore values; no parameter formula recalculation",
            "recalculateUnknownParameterGroups": False,
            "displayAllParameters": True,
            "communeNotApplicable": (
                "award declared maximum only after an explicit criterion maximum is available; "
                "never replace an API score silently"
            ),
        },
        provinceAggregatedScore=round(sum(scores), 2) if can_total else None,
        provinceAggregatedMaximum=sum(maxima) if can_total else None,
        datasets=datasets,
    )


def build_collected_snapshot(snapshot_dir: Path) -> NormalizedSnapshot:
    """Normalize a complete manifest created by ``collect_snapshot``."""

    manifest_path = snapshot_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise ValueError("Collected snapshot manifest is not complete")
    scope = manifest["scope"]
    if scope not in UNSUPPORTED_BY_SCOPE:
        raise ValueError(f"Unsupported collected scope: {scope}")
    unsupported = sorted(UNSUPPORTED_BY_SCOPE[scope])
    required = [group for group in GROUP_ORDER if group not in unsupported]
    captures = {capture["group"]: capture for capture in manifest["captures"]}
    if set(captures) != set(required) or manifest.get("expectedGroups") != required:
        raise ValueError("Collected manifest group set is inconsistent")

    formality_ids = {
        capture["payload"].get("formalityId", capture["payload"].get("formalityID"))
        for capture in captures.values()
        if capture["payload"].get("formalityId", capture["payload"].get("formalityID"))
    }
    if scope == "formality" and len(formality_ids) != 1:
        raise ValueError("Collected formality identity is inconsistent")
    formality_id = next(iter(formality_ids)) if formality_ids else None

    datasets = []
    for group in required:
        capture = captures[group]
        path = snapshot_dir / capture["file"]
        raw_bytes = path.read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest() != capture["sha256"]:
            raise ValueError(f"Collected raw hash changed for {group}")
        datasets.append(
            normalize_fixture(
                path,
                fixtures_root=snapshot_dir,
                group=group,
                period=manifest["period"],
                scope=scope,
                formality_id=formality_id,
            )
        )
    return _assemble_snapshot(
        manifest["period"],
        scope,
        formality_id,
        required,
        unsupported,
        [],
        datasets,
    )


def expected_groups() -> set[str]:
    return set(GROUP_ORDER)


assert expected_groups() == ALL_GROUPS
