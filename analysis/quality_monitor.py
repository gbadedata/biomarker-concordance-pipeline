"""
Quality monitoring.

VAF series  → Levey-Jennings control charts + Westgard rules (clinical lab standard).
Concordance → GA4GH-style threshold monitoring + Mann-Kendall trend test.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class WestgardRule(str, Enum):
    R1_2S  = "1_2s"
    R1_3S  = "1_3s"
    R2_2S  = "2_2s"
    R4_1S  = "R_4s"
    R4_1SX = "4_1s"
    R10X   = "10_x"


@dataclass
class WestgardViolation:
    rule:       WestgardRule
    run_index:  int
    run_id:     str
    value:      float
    is_warning: bool
    description: str


@dataclass
class LeveyJenningsResult:
    metric:     str
    n_runs:     int
    mean:       float
    sd:         float
    sd2_upper:  float
    sd2_lower:  float
    sd3_upper:  float
    sd3_lower:  float
    values:     list[float]
    run_ids:    list[str]
    violations: list[WestgardViolation]
    in_control: bool


class TrendDirection(str, Enum):
    STABLE    = "stable"
    DECLINING = "declining"
    IMPROVING = "improving"


@dataclass
class ConcordanceTrendResult:
    metric:               str
    variant_type:         str
    run_ids:              list[str]
    values:               list[float]
    threshold:            float
    trend:                TrendDirection
    mk_tau:               float
    mk_p:                 float
    below_threshold_runs: list[str]
    alert:                str | None


def apply_westgard_rules(
    values:  Sequence[float],
    run_ids: Sequence[str],
    mean:    float,
    sd:      float,
    metric:  str = "vaf",
) -> list[WestgardViolation]:
    vals = list(values)
    rids = list(run_ids)
    violations: list[WestgardViolation] = []

    for i, (v, rid) in enumerate(zip(vals, rids)):
        z = (v - mean) / sd if sd > 0 else 0.0

        if abs(z) > 3.0:
            violations.append(WestgardViolation(
                rule=WestgardRule.R1_3S, run_index=i, run_id=rid, value=v,
                is_warning=False,
                description=f"{metric} = {v:.4f} exceeds ±3SD ({mean:.4f} ± {3*sd:.4f})",
            ))
            continue

        if abs(z) > 2.0:
            violations.append(WestgardViolation(
                rule=WestgardRule.R1_2S, run_index=i, run_id=rid, value=v,
                is_warning=True, description=f"{metric} = {v:.4f} outside ±2SD (warning)",
            ))

        if i >= 1:
            z_prev = (vals[i - 1] - mean) / sd if sd > 0 else 0.0
            if abs(z) > 2.0 and abs(z_prev) > 2.0 and np.sign(z) == np.sign(z_prev):
                violations.append(WestgardViolation(
                    rule=WestgardRule.R2_2S, run_index=i, run_id=rid, value=v,
                    is_warning=False,
                    description=f"Two consecutive {metric} values beyond ±2SD same side",
                ))
            if abs(v - vals[i - 1]) > 4 * sd:
                violations.append(WestgardViolation(
                    rule=WestgardRule.R4_1S, run_index=i, run_id=rid, value=v,
                    is_warning=False,
                    description=f"Range between {rids[i-1]} and {rid} exceeds 4SD",
                ))

        if i >= 3:
            window = [(vals[j] - mean) / sd for j in range(i - 3, i + 1)]
            if all(w > 1.0 for w in window) or all(w < -1.0 for w in window):
                violations.append(WestgardViolation(
                    rule=WestgardRule.R4_1SX, run_index=i, run_id=rid, value=v,
                    is_warning=False,
                    description=f"Four consecutive {metric} values beyond ±1SD same side",
                ))

        if i >= 9:
            window = [(vals[j] - mean) for j in range(i - 9, i + 1)]
            if all(w > 0 for w in window) or all(w < 0 for w in window):
                violations.append(WestgardViolation(
                    rule=WestgardRule.R10X, run_index=i, run_id=rid, value=v,
                    is_warning=False,
                    description=f"Ten consecutive {metric} values on same side of mean",
                ))

    return violations


def build_levey_jennings(
    values:     Sequence[float],
    run_ids:    Sequence[str],
    metric:     str = "median_vaf",
    baseline_n: int = 20,
) -> LeveyJenningsResult:
    vals     = list(values)
    baseline = vals[:baseline_n]
    mean     = float(np.mean(baseline))
    sd       = float(np.std(baseline, ddof=1)) if len(baseline) > 1 else 0.0

    violations = apply_westgard_rules(vals, list(run_ids), mean, sd, metric)
    rejections = [v for v in violations if not v.is_warning]

    return LeveyJenningsResult(
        metric=metric, n_runs=len(vals), mean=mean, sd=sd,
        sd2_upper=mean + 2 * sd, sd2_lower=mean - 2 * sd,
        sd3_upper=mean + 3 * sd, sd3_lower=mean - 3 * sd,
        values=vals, run_ids=list(run_ids),
        violations=violations, in_control=len(rejections) == 0,
    )


def monitor_concordance_trend(
    run_ids:      Sequence[str],
    values:       Sequence[float],
    metric:       str,
    variant_type: str,
    threshold:    float,
    mk_alpha:     float = 0.05,
) -> ConcordanceTrendResult:
    vals    = list(values)
    run_ids = list(run_ids)

    mk  = stats.kendalltau(range(len(vals)), vals)
    tau = float(mk.statistic)
    p   = float(mk.pvalue)

    if p < mk_alpha:
        trend = TrendDirection.DECLINING if tau < 0 else TrendDirection.IMPROVING
    else:
        trend = TrendDirection.STABLE

    below = [rid for rid, v in zip(run_ids, vals) if v < threshold]

    alert = None
    if below or trend == TrendDirection.DECLINING:
        parts = []
        if below:
            parts.append(f"{metric} ({variant_type}) below {threshold:.3f} in: {', '.join(below)}")
        if trend == TrendDirection.DECLINING:
            parts.append(f"Declining trend detected (τ={tau:.3f}, p={p:.4f})")
        alert = " | ".join(parts)

    return ConcordanceTrendResult(
        metric=metric, variant_type=variant_type,
        run_ids=run_ids, values=vals, threshold=threshold,
        trend=trend, mk_tau=tau, mk_p=p,
        below_threshold_runs=below, alert=alert,
    )


def run_quality_monitoring(
    concordance_series: pd.DataFrame,
    vaf_series:         pd.DataFrame,
    thresholds:         dict | None = None,
) -> dict:
    if thresholds is None:
        thresholds = {
            "snv_f1": 0.98, "snv_precision": 0.98, "snv_recall": 0.98,
            "indel_f1": 0.95, "indel_precision": 0.95, "indel_recall": 0.95,
        }

    report: dict = {"concordance_trends": [], "vaf_control": []}

    for col, (metric, vtype) in {
        "snv_f1":          ("F1",        "SNP"),
        "snv_precision":   ("Precision", "SNP"),
        "snv_recall":      ("Recall",    "SNP"),
        "indel_f1":        ("F1",        "INDEL"),
        "indel_precision": ("Precision", "INDEL"),
        "indel_recall":    ("Recall",    "INDEL"),
    }.items():
        if col not in concordance_series.columns:
            continue
        r = monitor_concordance_trend(
            concordance_series["run_id"].tolist(),
            concordance_series[col].tolist(),
            metric, vtype, thresholds.get(col, 0.95),
        )
        report["concordance_trends"].append({
            "metric": metric, "variant_type": vtype,
            "trend": r.trend.value, "mk_tau": round(r.mk_tau, 4),
            "mk_p": round(r.mk_p, 4),
            "below_threshold_runs": r.below_threshold_runs,
            "alert": r.alert,
        })

    for col in ["median_vaf", "mean_vaf"]:
        if col not in vaf_series.columns:
            continue
        lj = build_levey_jennings(
            vaf_series[col].tolist(), vaf_series["run_id"].tolist(), col
        )
        report["vaf_control"].append({
            "metric": col, "mean": round(lj.mean, 4), "sd": round(lj.sd, 4),
            "sd2_upper": round(lj.sd2_upper, 4), "sd2_lower": round(lj.sd2_lower, 4),
            "sd3_upper": round(lj.sd3_upper, 4), "sd3_lower": round(lj.sd3_lower, 4),
            "in_control": lj.in_control,
            "violations": [
                {"rule": v.rule.value, "run_id": v.run_id, "value": round(v.value, 4),
                 "is_warning": v.is_warning, "description": v.description}
                for v in lj.violations
            ],
        })

    return report
