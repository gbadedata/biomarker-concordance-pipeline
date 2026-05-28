"""Shared pytest fixtures."""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def make_hapqy_summary(
    snv_precision=0.9921, snv_recall=0.9934, snv_f1=0.9928,
    indel_precision=0.9612, indel_recall=0.9703, indel_f1=0.9657,
) -> str:
    rows = [
        {"Type": "SNP",   "Filter": "PASS", "Subtype": "*",
         "TRUTH.TP": "412431", "QUERY.FP": "3245", "TRUTH.FN": "2701",
         "METRIC.Precision": str(snv_precision), "METRIC.Recall": str(snv_recall), "METRIC.F1_Score": str(snv_f1)},
        {"Type": "INDEL", "Filter": "PASS", "Subtype": "*",
         "TRUTH.TP": "51203",  "QUERY.FP": "2041", "TRUTH.FN": "1589",
         "METRIC.Precision": str(indel_precision), "METRIC.Recall": str(indel_recall), "METRIC.F1_Score": str(indel_f1)},
        {"Type": "SNP",   "Filter": "ALL",  "Subtype": "*",
         "TRUTH.TP": "420000", "QUERY.FP": "4000", "TRUTH.FN": "3000",
         "METRIC.Precision": "0.99", "METRIC.Recall": "0.99", "METRIC.F1_Score": "0.99"},
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
    return buf.getvalue()


@pytest.fixture
def hapqy_csv_passing(tmp_path) -> Path:
    p = tmp_path / "passing.summary.csv"
    p.write_text(make_hapqy_summary())
    return p


@pytest.fixture
def hapqy_csv_failing(tmp_path) -> Path:
    p = tmp_path / "failing.summary.csv"
    p.write_text(make_hapqy_summary(snv_f1=0.965, snv_precision=0.963))
    return p


@pytest.fixture
def synthetic_vaf_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 200
    positions = list(range(10_000, 10_000 + n))
    true_vafs = rng.beta(5, 5, size=n)
    rows = []
    for run_id in ["run_001", "run_002", "run_003"]:
        noise = rng.normal(0, 0.02, size=n)
        vafs  = np.clip(true_vafs + noise, 0.01, 0.99)
        for pos, vaf in zip(positions, vafs):
            rows.append({"chrom": "chr20", "pos": pos, "ref": "A", "alt": "T", "run_id": run_id, "vaf": float(vaf)})
    return pd.DataFrame(rows)


@pytest.fixture
def stable_concordance_series() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n = 20
    return pd.DataFrame({
        "run_id":          [f"run_{i:03d}" for i in range(n)],
        "snv_f1":          rng.normal(0.992, 0.001, n).clip(0.98, 1.0).tolist(),
        "snv_precision":   rng.normal(0.992, 0.001, n).clip(0.98, 1.0).tolist(),
        "snv_recall":      rng.normal(0.993, 0.001, n).clip(0.98, 1.0).tolist(),
        "indel_f1":        rng.normal(0.966, 0.002, n).clip(0.95, 1.0).tolist(),
        "indel_precision": rng.normal(0.961, 0.002, n).clip(0.95, 1.0).tolist(),
        "indel_recall":    rng.normal(0.971, 0.002, n).clip(0.95, 1.0).tolist(),
    })


@pytest.fixture
def declining_concordance_series() -> pd.DataFrame:
    n   = 20
    rng = np.random.default_rng(1)
    base = np.linspace(0.995, 0.960, n)
    return pd.DataFrame({
        "run_id":          [f"run_{i:03d}" for i in range(n)],
        "snv_f1":          (base + rng.normal(0, 0.001, n)).tolist(),
        "snv_precision":   (base + rng.normal(0, 0.001, n)).tolist(),
        "snv_recall":      (base + rng.normal(0, 0.001, n)).tolist(),
        "indel_f1":        np.full(n, 0.967).tolist(),
        "indel_precision": np.full(n, 0.962).tolist(),
        "indel_recall":    np.full(n, 0.972).tolist(),
    })


@pytest.fixture
def stable_vaf_series() -> pd.DataFrame:
    rng = np.random.default_rng(2)
    n   = 20
    return pd.DataFrame({
        "run_id":     [f"run_{i:03d}" for i in range(n)],
        "median_vaf": rng.normal(0.48, 0.005, n).clip(0.40, 0.55).tolist(),
        "mean_vaf":   rng.normal(0.48, 0.005, n).clip(0.40, 0.55).tolist(),
    })


@pytest.fixture
def out_of_control_vaf_series() -> pd.DataFrame:
    rng  = np.random.default_rng(3)
    n    = 20
    vals = rng.normal(0.48, 0.005, n).tolist()
    vals[15] = 0.55  # triggers 1_3s
    return pd.DataFrame({
        "run_id":     [f"run_{i:03d}" for i in range(n)],
        "median_vaf": vals,
        "mean_vaf":   vals,
    })
