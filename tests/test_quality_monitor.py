"""Tests for analysis/quality_monitor.py."""

from __future__ import annotations

import math
import numpy as np
import pytest

from analysis.quality_monitor import (
    WestgardRule,
    apply_westgard_rules,
    build_levey_jennings,
    monitor_concordance_trend,
    TrendDirection,
)


class TestWestgardRules:
    mean = 0.48
    sd   = 0.01
    n    = 20

    def _stable_vals(self):
        """Deterministic values within ±0.6SD — no rejection rule possible."""
        return [self.mean + self.sd * 0.3 * math.sin(i * 0.7) for i in range(self.n)]

    def _run_ids(self):
        return [f"run_{i:03d}" for i in range(self.n)]

    def test_no_violations_for_stable_series(self):
        viol = apply_westgard_rules(self._stable_vals(), self._run_ids(), self.mean, self.sd)
        assert all(v.is_warning for v in viol)

    def test_1_3s_triggered(self):
        vals = self._stable_vals()
        vals[5] = self.mean + 3.5 * self.sd
        viol = apply_westgard_rules(vals, self._run_ids(), self.mean, self.sd)
        assert WestgardRule.R1_3S in {v.rule for v in viol}

    def test_1_2s_is_warning(self):
        vals = self._stable_vals()
        vals[3] = self.mean + 2.2 * self.sd
        viol = apply_westgard_rules(vals, self._run_ids(), self.mean, self.sd)
        warnings = [v for v in viol if v.is_warning and v.run_index == 3]
        assert len(warnings) > 0

    def test_10x_triggered(self):
        vals = [self.mean + 0.005 for _ in range(self.n)]
        viol = apply_westgard_rules(vals, self._run_ids(), self.mean, self.sd)
        assert WestgardRule.R10X in {v.rule for v in viol}

    def test_2_2s_triggered(self):
        vals = self._stable_vals()
        vals[8] = self.mean + 2.1 * self.sd
        vals[9] = self.mean + 2.1 * self.sd
        viol = apply_westgard_rules(vals, self._run_ids(), self.mean, self.sd)
        assert WestgardRule.R2_2S in {v.rule for v in viol}


class TestLeveyJennings:
    def test_in_control_series(self):
        mean = 0.48
        sd = 0.01
        n = 20
        vals = [mean + sd * 0.3 * math.sin(i * 0.7) for i in range(n)]
        run_ids = [f"run_{i:03d}" for i in range(n)]
        lj = build_levey_jennings(vals, run_ids)
        rejections = [v for v in lj.violations if not v.is_warning]
        assert len(rejections) == 0
        assert lj.in_control is True

    def test_out_of_control(self, out_of_control_vaf_series):
        lj = build_levey_jennings(
            out_of_control_vaf_series["median_vaf"].tolist(),
            out_of_control_vaf_series["run_id"].tolist(),
        )
        assert lj.in_control is False

    def test_control_limits_correct(self, stable_vaf_series):
        lj = build_levey_jennings(
            stable_vaf_series["median_vaf"].tolist(),
            stable_vaf_series["run_id"].tolist(),
        )
        assert abs(lj.sd2_upper - (lj.mean + 2 * lj.sd)) < 1e-9
        assert abs(lj.sd3_lower - (lj.mean - 3 * lj.sd)) < 1e-9


class TestConcordanceTrend:
    def test_stable_no_alert(self, stable_concordance_series):
        r = monitor_concordance_trend(
            stable_concordance_series["run_id"].tolist(),
            stable_concordance_series["snv_f1"].tolist(),
            "F1", "SNP", threshold=0.98,
        )
        assert r.trend == TrendDirection.STABLE
        assert r.alert is None

    def test_declining_detected(self, declining_concordance_series):
        r = monitor_concordance_trend(
            declining_concordance_series["run_id"].tolist(),
            declining_concordance_series["snv_f1"].tolist(),
            "F1", "SNP", threshold=0.98,
        )
        assert r.trend == TrendDirection.DECLINING
        assert r.alert is not None

    def test_below_threshold_captured(self, declining_concordance_series):
        r = monitor_concordance_trend(
            declining_concordance_series["run_id"].tolist(),
            declining_concordance_series["snv_f1"].tolist(),
            "F1", "SNP", threshold=0.98,
        )
        assert len(r.below_threshold_runs) > 0

    def test_mk_tau_in_range(self, stable_concordance_series):
        r = monitor_concordance_trend(
            stable_concordance_series["run_id"].tolist(),
            stable_concordance_series["snv_f1"].tolist(),
            "F1", "SNP", threshold=0.98,
        )
        assert -1.0 <= r.mk_tau <= 1.0
