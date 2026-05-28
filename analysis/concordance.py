"""
Concordance analysis against the GIAB HG001 v4.2.1 truth set.

Parses hap.py summary CSV and computes per-variant-type accuracy metrics.
Flags runs below configurable thresholds and emits structured results
for database storage and dashboard rendering.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

VariantType = Literal["SNP", "INDEL"]


@dataclass
class ConcordanceMetrics:
    sample_id:       str
    run_id:          str
    variant_type:    VariantType
    true_positives:  float
    false_positives: float
    false_negatives: float
    precision:       float
    recall:          float
    f1_score:        float
    specificity:     float
    cohen_kappa:     float
    precision_pass:  bool
    recall_pass:     bool
    f1_pass:         bool
    hapqy_filter:    str


@dataclass
class ConcordanceReport:
    sample_id:    str
    run_id:       str
    hapqy_file:   str
    snv:          ConcordanceMetrics
    indel:        ConcordanceMetrics
    overall_pass: bool
    alerts:       list[str]


def _cohen_kappa(tp: float, fp: float, fn: float, tn_estimate: float = 1e6) -> float:
    """
    Cohen's kappa treating variant calling as binary classification.
    tn_estimate: conservative lower bound for true-negative sites in the
    high-confidence region — exact TN requires the BED region size.
    """
    n = tp + fp + fn + tn_estimate
    if n == 0:
        return 0.0
    p_o = (tp + tn_estimate) / n
    p_e = ((tp + fp) / n * (tp + fn) / n) + ((fn + tn_estimate) / n * (fp + tn_estimate) / n)
    return (p_o - p_e) / (1 - p_e) if (1 - p_e) != 0 else 1.0


def _parse_hapqy_summary(csv_path: Path) -> dict[str, dict]:
    """
    Parse hap.py summary.csv.
    Returns dict keyed by variant type (SNP, INDEL) for PASS filter, ALL subtype rows.
    """
    results: dict[str, dict] = {}
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            vtype = row.get("Type", "").upper()
            if row.get("Filter") == "PASS" and row.get("Subtype") == "*" and vtype in ("SNP", "INDEL"):
                results[vtype] = row

    missing = {"SNP", "INDEL"} - set(results.keys())
    if missing:
        raise ValueError(f"hap.py summary missing rows for: {missing}. Check {csv_path}.")
    return results


def compute_concordance(
    sample_id:           str,
    run_id:              str,
    hapqy_csv:           Path,
    min_snv_precision:   float = 0.98,
    min_snv_recall:      float = 0.98,
    min_snv_f1:          float = 0.98,
    min_indel_precision: float = 0.95,
    min_indel_recall:    float = 0.95,
    min_indel_f1:        float = 0.95,
) -> ConcordanceReport:
    hapqy_csv = Path(hapqy_csv)
    if not hapqy_csv.exists():
        raise FileNotFoundError(f"hap.py summary not found: {hapqy_csv}")

    raw    = _parse_hapqy_summary(hapqy_csv)
    alerts: list[str] = []
    metrics: dict[str, ConcordanceMetrics] = {}

    thresholds = {
        "SNP":   (min_snv_precision,   min_snv_recall,   min_snv_f1),
        "INDEL": (min_indel_precision, min_indel_recall, min_indel_f1),
    }

    for vtype, row in raw.items():
        tp  = float(row.get("TRUTH.TP", 0))
        fp  = float(row.get("QUERY.FP", 0))
        fn  = float(row.get("TRUTH.FN", 0))
        prec = float(row.get("METRIC.Precision", 0))
        rec  = float(row.get("METRIC.Recall",    0))
        f1   = float(row.get("METRIC.F1_Score",  0))
        spec = 1.0 - fp / (fp + 1e6)
        kappa = _cohen_kappa(tp, fp, fn)

        min_prec, min_rec, min_f1 = thresholds[vtype]  # type: ignore[literal-required]
        prec_pass = prec >= min_prec
        rec_pass  = rec  >= min_rec
        f1_pass   = f1   >= min_f1

        if not prec_pass:
            alerts.append(f"{vtype} precision {prec:.4f} below threshold {min_prec:.4f}")
        if not rec_pass:
            alerts.append(f"{vtype} recall {rec:.4f} below threshold {min_rec:.4f}")
        if not f1_pass:
            alerts.append(f"{vtype} F1 {f1:.4f} below threshold {min_f1:.4f}")

        metrics[vtype] = ConcordanceMetrics(
            sample_id=sample_id, run_id=run_id,
            variant_type=vtype,  # type: ignore[arg-type]
            true_positives=tp, false_positives=fp, false_negatives=fn,
            precision=prec, recall=rec, f1_score=f1,
            specificity=spec, cohen_kappa=kappa,
            precision_pass=prec_pass, recall_pass=rec_pass, f1_pass=f1_pass,
            hapqy_filter=row.get("Filter", "PASS"),
        )

    return ConcordanceReport(
        sample_id=sample_id, run_id=run_id, hapqy_file=str(hapqy_csv),
        snv=metrics["SNP"], indel=metrics["INDEL"],
        overall_pass=len(alerts) == 0, alerts=alerts,
    )


def report_to_dict(report: ConcordanceReport) -> dict:
    return {
        "sample_id":    report.sample_id,
        "run_id":       report.run_id,
        "hapqy_file":   report.hapqy_file,
        "overall_pass": report.overall_pass,
        "alerts":       report.alerts,
        "snv":          asdict(report.snv),
        "indel":        asdict(report.indel),
    }


def save_report(report: ConcordanceReport, output_path: Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as fh:
        json.dump(report_to_dict(report), fh, indent=2)
