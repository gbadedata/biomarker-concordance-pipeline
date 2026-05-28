"""
Biomarker reproducibility analysis.

Extracts variant allele frequency (VAF) from replicate VCFs and quantifies
inter-run consistency using ICC(A,1), Bland-Altman, and CV.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import pingouin as pg

logger = logging.getLogger(__name__)


@dataclass
class ICCResult:
    sample_id:      str
    n_variants:     int
    n_reps:         int
    icc:            float
    ci_lower:       float
    ci_upper:       float
    f_value:        float
    p_value:        float
    pass_threshold: bool


@dataclass
class BlandAltmanResult:
    sample_id:         str
    run_a:             str
    run_b:             str
    n_variants:        int
    mean_diff:         float
    sd_diff:           float
    loa_upper:         float
    loa_lower:         float
    proportional_bias: bool
    bias_significant:  bool


@dataclass
class CVResult:
    sample_id:        str
    n_variants:       int
    median_cv:        float
    p90_cv:           float
    fraction_cv_gt15: float


@dataclass
class ReproducibilityReport:
    sample_id:    str
    run_ids:      list[str]
    n_variants:   int
    icc:          ICCResult
    bland_altman: list[BlandAltmanResult]
    cv:           CVResult
    overall_pass: bool
    alerts:       list[str]


def _extract_vaf(vcf_path: Path) -> dict[tuple, float]:
    """Extract VAF from FORMAT/AD for biallelic PASS variants with DP >= 10."""
    try:
        import cyvcf2
    except ImportError:
        raise ImportError("cyvcf2 required: pip install cyvcf2")

    vcf  = cyvcf2.VCF(str(vcf_path))
    vafs: dict[tuple, float] = {}

    for v in vcf:
        if len(v.ALT) != 1:
            continue
        if v.FILTER and v.FILTER != "PASS":
            continue
        ad = v.format("AD")
        if ad is None:
            continue
        ad0, ad1 = int(ad[0][0]), int(ad[0][1])
        total = ad0 + ad1
        if total < 10:
            continue
        vafs[(v.CHROM, v.POS, v.REF, v.ALT[0])] = ad1 / total

    vcf.close()
    return vafs


def extract_vaf_panel(run_vcfs: dict[str, Path], min_reps: int = 2) -> pd.DataFrame:
    """Return long-format VAF dataframe for variants present in >= min_reps runs."""
    per_run = {rid: _extract_vaf(p) for rid, p in run_vcfs.items()}

    counts: dict[tuple, int] = {}
    for vafs in per_run.values():
        for k in vafs:
            counts[k] = counts.get(k, 0) + 1

    shared = {k for k, c in counts.items() if c >= min_reps}

    rows = [
        {"chrom": k[0], "pos": k[1], "ref": k[2], "alt": k[3], "run_id": rid, "vaf": vafs[k]}
        for rid, vafs in per_run.items()
        for k in shared if k in vafs
    ]
    return pd.DataFrame(rows)


def compute_icc(sample_id: str, vaf_df: pd.DataFrame, min_icc: float = 0.90) -> ICCResult:
    if vaf_df.empty:
        raise ValueError("VAF dataframe is empty.")

    icc_df  = pg.intraclass_corr(
        data=vaf_df.rename(columns={"vaf": "ratings"}),
        targets="pos", raters="run_id", ratings="ratings",
    )

    mask = icc_df["Type"].isin(["ICC2", "ICC(A,1)"])
    if not mask.any():
        raise ValueError(f"ICC(A,1) not found. Available: {icc_df['Type'].tolist()}")

    row     = icc_df[mask].iloc[0]
    icc_val = float(row["ICC"])
    f_val   = float(row["F"])
    p_val   = float(row["pval"])
    ci_col  = "CI95%" if "CI95%" in icc_df.columns else "CI95"
    ci_arr  = row[ci_col]

    return ICCResult(
        sample_id=sample_id,
        n_variants=vaf_df["pos"].nunique(),
        n_reps=vaf_df["run_id"].nunique(),
        icc=icc_val,
        ci_lower=float(ci_arr[0]),
        ci_upper=float(ci_arr[1]),
        f_value=f_val,
        p_value=p_val,
        pass_threshold=icc_val >= min_icc,
    )


def compute_bland_altman(sample_id: str, vaf_df: pd.DataFrame) -> list[BlandAltmanResult]:
    results = []
    for run_a, run_b in combinations(sorted(vaf_df["run_id"].unique()), 2):
        a = vaf_df[vaf_df["run_id"] == run_a].set_index("pos")["vaf"]
        b = vaf_df[vaf_df["run_id"] == run_b].set_index("pos")["vaf"]
        common = a.index.intersection(b.index)
        if len(common) < 5:
            continue
        diffs  = a.loc[common].values - b.loc[common].values
        means  = (a.loc[common].values + b.loc[common].values) / 2
        mean_d = float(np.mean(diffs))
        sd_d   = float(np.std(diffs, ddof=1))
        prop   = abs(float(np.corrcoef(means, diffs)[0, 1])) > 0.3
        results.append(BlandAltmanResult(
            sample_id=sample_id, run_a=run_a, run_b=run_b,
            n_variants=len(common),
            mean_diff=mean_d, sd_diff=sd_d,
            loa_upper=mean_d + 1.96 * sd_d,
            loa_lower=mean_d - 1.96 * sd_d,
            proportional_bias=prop,
            bias_significant=abs(mean_d) > 0.05,
        ))
    return results


def compute_cv(sample_id: str, vaf_df: pd.DataFrame) -> CVResult:
    pv = vaf_df.groupby("pos")["vaf"].agg(mean="mean", std="std").dropna()
    pv["cv"] = (pv["std"] / pv["mean"]) * 100
    return CVResult(
        sample_id=sample_id,
        n_variants=len(pv),
        median_cv=float(pv["cv"].median()),
        p90_cv=float(pv["cv"].quantile(0.90)),
        fraction_cv_gt15=float((pv["cv"] > 15).mean()),
    )


def compute_reproducibility(
    sample_id: str,
    run_vcfs:  dict[str, Path],
    min_icc:   float = 0.90,
    max_cv:    float = 0.15,
) -> ReproducibilityReport:
    if len(run_vcfs) < 2:
        raise ValueError(f"Need at least 2 runs; got {len(run_vcfs)}.")

    vaf_df = extract_vaf_panel(run_vcfs)
    if vaf_df.empty:
        raise ValueError("No shared variants found across runs.")

    icc = compute_icc(sample_id, vaf_df, min_icc=min_icc)
    ba  = compute_bland_altman(sample_id, vaf_df)
    cv  = compute_cv(sample_id, vaf_df)

    alerts: list[str] = []
    if not icc.pass_threshold:
        alerts.append(f"ICC {icc.icc:.3f} below threshold {min_icc:.3f}")
    if cv.median_cv / 100 > max_cv:
        alerts.append(f"Median CV {cv.median_cv:.1f}% exceeds threshold {max_cv * 100:.1f}%")
    for b in ba:
        if b.bias_significant:
            alerts.append(f"Significant VAF bias between {b.run_a} and {b.run_b}: {b.mean_diff:.4f}")

    return ReproducibilityReport(
        sample_id=sample_id, run_ids=list(run_vcfs.keys()),
        n_variants=vaf_df["pos"].nunique(),
        icc=icc, bland_altman=ba, cv=cv,
        overall_pass=len(alerts) == 0, alerts=alerts,
    )
