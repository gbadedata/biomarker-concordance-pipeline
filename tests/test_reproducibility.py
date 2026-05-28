"""Tests for analysis/reproducibility.py."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from analysis.reproducibility import compute_bland_altman, compute_cv, compute_icc


class TestICC:
    def test_high_icc_for_low_noise(self, synthetic_vaf_df):
        r = compute_icc("HG001", synthetic_vaf_df, min_icc=0.90)
        assert r.icc > 0.85
        assert r.n_variants == 200
        assert r.n_reps == 3

    def test_ci_contains_point_estimate(self, synthetic_vaf_df):
        r = compute_icc("HG001", synthetic_vaf_df)
        # pingouin rounds CI to 2dp — compare at that precision
        icc_r = round(r.icc, 2)
        assert r.ci_lower <= icc_r <= r.ci_upper

    def test_icc_in_valid_range(self, synthetic_vaf_df):
        r = compute_icc("HG001", synthetic_vaf_df)
        assert 0.0 <= r.icc <= 1.0

    def test_low_icc_for_high_noise(self):
        rng = np.random.default_rng(99)
        n   = 100
        positions = list(range(1000, 1000 + n))
        true_vafs = rng.beta(5, 5, size=n)
        rows = []
        for run_id in ["r1", "r2", "r3"]:
            noise = rng.normal(0, 0.15, size=n)
            vafs  = np.clip(true_vafs + noise, 0.01, 0.99)
            for pos, vaf in zip(positions, vafs):
                rows.append({"pos": pos, "run_id": run_id, "vaf": float(vaf)})
        r = compute_icc("noisy", pd.DataFrame(rows), min_icc=0.90)
        assert r.icc < 0.95

    def test_empty_df_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compute_icc("s", pd.DataFrame())


class TestBlandAltman:
    def test_three_runs_give_three_pairs(self, synthetic_vaf_df):
        assert len(compute_bland_altman("HG001", synthetic_vaf_df)) == 3

    def test_loa_spans_mean_diff(self, synthetic_vaf_df):
        for ba in compute_bland_altman("HG001", synthetic_vaf_df):
            assert ba.loa_lower < ba.mean_diff < ba.loa_upper

    def test_no_bias_for_low_noise(self, synthetic_vaf_df):
        for ba in compute_bland_altman("HG001", synthetic_vaf_df):
            assert not ba.bias_significant

    def test_detects_systematic_bias(self):
        rng = np.random.default_rng(7)
        n = 150
        positions = list(range(5000, 5000 + n))
        true_vafs = rng.beta(5, 5, size=n)
        rows = []
        for i, run_id in enumerate(["r1", "r2"]):
            offset = 0.10 if i == 1 else 0.0
            vafs = np.clip(true_vafs + offset + rng.normal(0, 0.01, n), 0.01, 0.99)
            for pos, vaf in zip(positions, vafs):
                rows.append({"pos": pos, "run_id": run_id, "vaf": float(vaf)})
        results = compute_bland_altman("biased", pd.DataFrame(rows))
        assert results[0].bias_significant


class TestCV:
    def test_low_cv_for_low_noise(self, synthetic_vaf_df):
        r = compute_cv("HG001", synthetic_vaf_df)
        assert r.median_cv < 10.0
        assert r.n_variants == 200

    def test_fraction_in_range(self, synthetic_vaf_df):
        r = compute_cv("HG001", synthetic_vaf_df)
        assert 0.0 <= r.fraction_cv_gt15 <= 1.0
