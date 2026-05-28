"""Tests for analysis/concordance.py."""

from __future__ import annotations

import pytest

from analysis.concordance import (
    _cohen_kappa,
    _parse_hapqy_summary,
    compute_concordance,
    report_to_dict,
)


class TestCohenKappa:
    def test_perfect_agreement(self):
        assert _cohen_kappa(tp=100_000, fp=0, fn=0) > 0.99

    def test_zero_tp(self):
        assert _cohen_kappa(tp=0, fp=100, fn=100) <= 0

    def test_moderate_agreement(self):
        k = _cohen_kappa(tp=400_000, fp=4_000, fn=4_000)
        assert 0.95 < k < 1.0

    def test_returns_float(self):
        assert isinstance(_cohen_kappa(tp=50_000, fp=500, fn=300), float)


class TestParseHapqySummary:
    def test_parses_snp_and_indel(self, hapqy_csv_passing):
        result = _parse_hapqy_summary(hapqy_csv_passing)
        assert "SNP" in result and "INDEL" in result

    def test_ignores_all_filter(self, hapqy_csv_passing):
        assert len(_parse_hapqy_summary(hapqy_csv_passing)) == 2

    def test_missing_type_raises(self, tmp_path):
        p = tmp_path / "bad.csv"
        p.write_text(
            "Type,Filter,Subtype,TRUTH.TP,QUERY.FP,TRUTH.FN,"
            "METRIC.Precision,METRIC.Recall,METRIC.F1_Score\n"
            "SNP,PASS,*,100,5,3,0.95,0.97,0.96\n"
        )
        with pytest.raises(ValueError, match="INDEL"):
            _parse_hapqy_summary(p)


class TestComputeConcordance:
    def test_passing_run(self, hapqy_csv_passing):
        r = compute_concordance("HG001", "run_001", hapqy_csv_passing)
        assert r.overall_pass is True
        assert r.snv.f1_score > 0.98

    def test_failing_run_generates_alerts(self, hapqy_csv_failing):
        r = compute_concordance("HG001", "run_002", hapqy_csv_failing)
        assert r.overall_pass is False
        assert len(r.alerts) > 0

    def test_metrics_in_valid_range(self, hapqy_csv_passing):
        r = compute_concordance("HG001", "run_003", hapqy_csv_passing)
        for m in [r.snv, r.indel]:
            assert 0 <= m.precision <= 1
            assert 0 <= m.recall <= 1
            assert 0 <= m.f1_score <= 1
            assert -1 <= m.cohen_kappa <= 1

    def test_custom_threshold_fails_good_data(self, hapqy_csv_passing):
        r = compute_concordance("HG001", "run_004", hapqy_csv_passing, min_snv_f1=0.9999)
        assert r.overall_pass is False

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            compute_concordance("s", "r", tmp_path / "missing.csv")

    def test_report_serialisable(self, hapqy_csv_passing):
        import json

        r = compute_concordance("HG001", "run_005", hapqy_csv_passing)
        json.dumps(report_to_dict(r))
