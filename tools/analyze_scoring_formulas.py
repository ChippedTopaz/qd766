"""Infer and verify explanatory score formulas against the captured M0 fixtures.

This script is offline. It never calls DVCQG and never rewrites raw fixtures.
The score returned by the API remains authoritative; the formulas below are
diagnostic evidence for explaining how a score could be improved.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

TOLERANCE = 0.015


def ratio(numerator: float | int | None, denominator: float | int | None) -> float:
    return (numerator or 0) / denominator if denominator else 0.0


def load_records(root: Path, group: str):
    for path in sorted((root / "tests/fixtures" / group).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))["data"]
        if "overview" in data:
            yield path.name, data["overview"]
            for record in data["evaluation"]:
                yield path.name, record
        else:
            yield path.name, data["parent"]
            for record in data["children"]:
                yield path.name, record


def evidence(errors: list[float], observations: int | None = None) -> dict:
    count = len(errors) if observations is None else observations
    return {
        "observations": count,
        "maxAbsoluteError": round(max(errors, default=0), 12),
        "meanAbsoluteError": round(sum(errors) / len(errors), 12) if errors else 0,
        "tolerance": TOLERANCE,
        "withinTolerance": sum(error <= TOLERANCE for error in errors),
        "result": "PASS" if errors and all(error <= TOLERANCE for error in errors) else "FAIL",
    }


def analyze(root: Path) -> dict:
    formulas: list[dict] = []

    # Metric-code responses: transparency.
    errors = []
    observations = 0
    for _, record in load_records(root, "transparency"):
        for metric in record["metrics"]:
            if metric["score"] is None:
                continue
            predicted = metric["maxScore"] * (metric["ratio"] or 0) / 100
            errors.append(abs(predicted - metric["score"]))
            observations += 1
    formulas.append(
        {
            "group": "transparency",
            "status": "verified-on-m0",
            "formula": "score = maxScore * ratio / 100",
            "rounding": "API exposes score to two decimals",
            "evidence": evidence(errors, observations),
        }
    )

    # Satisfaction has three scored metrics and two classification-only metrics.
    satisfaction_errors: dict[str, list[float]] = defaultdict(list)
    for _, record in load_records(root, "handling-satisfaction"):
        for metric in record["metrics"]:
            if metric["score"] is None:
                continue
            denominator = metric["denominator"]
            raw_ratio = ratio(metric["numerator"], denominator)
            if metric["code"] == "DOSSIER_RECEIVING_SATISFACTION":
                predicted = min(6, 6 * raw_ratio / 0.9) if denominator else 0
            else:
                predicted = 6 * raw_ratio if denominator else 6
            satisfaction_errors[metric["code"]].append(
                abs(predicted - metric["score"])
            )
    satisfaction_descriptions = {
        "DOSSIER_RECEIVING_SATISFACTION": (
            "score = 0 when denominator = 0; otherwise "
            "min(6, 6 * numerator / denominator / 0.90)"
        ),
        "PETITION_PROCESSING_ON_TIME": (
            "score = 6 when denominator = 0; otherwise "
            "6 * numerator / denominator"
        ),
        "PETITION_HANDLING_SATISFACTION": (
            "score = 6 when denominator = 0; otherwise "
            "6 * numerator / denominator"
        ),
    }
    for code, description in satisfaction_descriptions.items():
        formulas.append(
            {
                "group": "handling-satisfaction",
                "metricCode": code,
                "status": "verified-on-m0",
                "formula": description,
                "evidence": evidence(satisfaction_errors[code]),
            }
        )

    # Digitization metrics. Null scores are preserved and excluded from fitting.
    digitized_errors: dict[str, list[float]] = defaultdict(list)
    null_scores: dict[str, int] = defaultdict(int)
    for _, record in load_records(root, "dossier-digitized"):
        for metric in record["metrics"]:
            code = metric["code"]
            if metric["score"] is None:
                null_scores[code] += 1
                continue
            threshold = 80 if code == "REUSED_DIGITIZED_DATA" else 100
            predicted = min(
                metric["maxScore"],
                metric["maxScore"] * (metric["ratio"] or 0) / threshold,
            )
            digitized_errors[code].append(abs(predicted - metric["score"]))
    for code in sorted(digitized_errors):
        threshold = 80 if code == "REUSED_DIGITIZED_DATA" else 100
        status = (
            "consistent-only-zero-observations"
            if code == "SYNCED_WITH_DVCQG_PERSONAL_STORAGE"
            else "verified-on-m0"
        )
        item = {
            "group": "dossier-digitized",
            "metricCode": code,
            "status": status,
            "formula": f"score = min(maxScore, maxScore * ratio / {threshold})",
            "nullScoresExcluded": null_scores[code],
            "evidence": evidence(digitized_errors[code]),
        }
        if status != "verified-on-m0":
            item["limitation"] = (
                "All non-null M0 observations have ratio=0, so a positive-rate "
                "case is required before the slope can be verified."
            )
        formulas.append(item)

    # Progress is directly reproducible from two response parameters.
    errors = []
    for _, record in load_records(root, "dvc-progress-tree"):
        predicted = 20 * ratio(record["totalOnTime"], record["totalReceived"])
        actual = record.get("totalScore", record.get("score"))
        errors.append(abs(predicted - actual))
    formulas.append(
        {
            "group": "dvc-progress-tree",
            "status": "verified-on-m0",
            "formula": "score = 20 * totalOnTime / totalReceived",
            "zeroDenominator": "No zero-denominator observation in M0; behavior unresolved",
            "evidence": evidence(errors),
        }
    )

    # Online service: keep the parameters visible, but do not promote the
    # dossier-ratio candidate to a formula unless its residual is stable.
    components = []
    for path in sorted((root / "tests/fixtures/provide-online-tree").glob("*.json")):
        parent = json.loads(path.read_text(encoding="utf-8"))["data"]["parent"]
        online_ratio = ratio(parent["onlineDossierCount"], parent["onlineServiceTotal"])
        components.append(parent["totalScore"] - 4 * online_ratio)
    baseline = sum(components) / len(components)
    errors = [abs(value - baseline) for value in components]
    formulas.append(
        {
            "group": "provide-online-tree",
            "status": "unresolved-on-m0",
            "candidateComponent": "4 * onlineDossierCount / onlineServiceTotal",
            "candidateVerified": False,
            "observedResidualForPhuTho": round(baseline, 12),
            "doNotImplementAsCompleteFormula": True,
            "limitation": (
                "The completed-month fixture makes the residual vary beyond the "
                "declared tolerance. The candidate is not a verified component, "
                "and the available observations cannot identify a complete formula."
            ),
            "evidence": evidence(errors),
        }
    )

    # Online payment decomposes into a 6-point dossier component and two
    # 2-point-ish formality components. The middle component caps at 2.
    errors = []
    for _, record in load_records(root, "formality-online-payment-tree"):
        dossier = ratio(
            record["totalDossierOnlinePaymentSuccess"],
            record["totalDossierFinancialObligation"],
        )
        online_formality = ratio(
            record["totalDossierOnlineFormalityPaymentSuccess"],
            record["totalFeeFormality"],
        )
        fee_dossier_formality = ratio(
            record["totalFeeDossierFormality"], record["totalFeeFormality"]
        )
        predicted = (
            6 * dossier
            + min(2, 2.5 * online_formality)
            + 2.5 * fee_dossier_formality
        )
        errors.append(abs(predicted - record["totalScore"]))
    formulas.append(
        {
            "group": "formality-online-payment-tree",
            "status": "verified-on-m0",
            "formula": (
                "score = 6*A + min(2, 2.5*B) + 2.5*C; "
                "A=totalDossierOnlinePaymentSuccess/totalDossierFinancialObligation; "
                "B=totalDossierOnlineFormalityPaymentSuccess/totalFeeFormality; "
                "C=totalFeeDossierFormality/totalFeeFormality"
            ),
            "zeroDenominator": "Each ratio is treated as 0 in M0 zero-denominator observations",
            "evidence": evidence(errors),
        }
    )

    return {
        "schemaVersion": 1,
        "source": "tests/fixtures M0 captured 2026-09-26",
        "policy": {
            "authoritativeValue": "API response score/totalScore",
            "inferredFormulaUse": "diagnostic explanation and improvement analysis only",
            "rawResponsesMutated": False,
            "legalOrOfficialFormulaClaimed": False,
        },
        "periodSemantics": {
            "userChoices": ["month", "quarter", "year"],
            "handlingSatisfactionTransport": "inclusive fromDate/toDate derived from the selected period",
            "freeDateSelection": False,
        },
        "formulas": formulas,
        "result": (
            "PASS"
            if all(f["evidence"]["result"] == "PASS" for f in formulas)
            else "INCOMPLETE"
            if all(
                f["evidence"]["result"] == "PASS"
                or f.get("status") == "unresolved-on-m0"
                for f in formulas
            )
            else "FAIL"
        ),
        "resultScope": "Captured M0 fixtures only; unresolved formulas remain explicitly non-executable",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = analyze(args.root)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")
    raise SystemExit(0 if report["result"] in {"PASS", "INCOMPLETE"} else 1)
