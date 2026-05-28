"""Pydantic v2 request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PipelineRunCreate(BaseModel):
    run_id:       str = Field(..., min_length=1, max_length=128)
    sample_id:    str = Field(..., min_length=1, max_length=128)
    replicate:    int = Field(..., ge=1)
    nextflow_run: str | None = None


class PipelineRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:           uuid.UUID
    run_id:       str
    sample_id:    str
    replicate:    int
    status:       str
    nextflow_run: str | None
    created_at:   datetime
    completed_at: datetime | None


class PipelineRunUpdate(BaseModel):
    status:       str | None      = None
    completed_at: datetime | None = None


class ConcordanceResultCreate(BaseModel):
    run_id:          uuid.UUID
    variant_type:    Literal["SNP", "INDEL"]
    true_positives:  float = Field(..., ge=0)
    false_positives: float = Field(..., ge=0)
    false_negatives: float = Field(..., ge=0)
    precision:       float = Field(..., ge=0, le=1)
    recall:          float = Field(..., ge=0, le=1)
    f1_score:        float = Field(..., ge=0, le=1)
    specificity:     float = Field(..., ge=0, le=1)
    cohen_kappa:     float = Field(..., ge=-1, le=1)
    precision_pass:  bool
    recall_pass:     bool
    f1_pass:         bool
    hapqy_file:      str | None = None


class ConcordanceResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:             uuid.UUID
    run_id:         uuid.UUID
    variant_type:   str
    precision:      float
    recall:         float
    f1_score:       float
    specificity:    float
    cohen_kappa:    float
    precision_pass: bool
    recall_pass:    bool
    f1_pass:        bool
    created_at:     datetime


class ConcordanceSummaryResponse(BaseModel):
    sample_id:            str
    n_runs:               int
    snv_f1_mean:          float
    snv_f1_min:           float
    snv_precision_mean:   float
    snv_recall_mean:      float
    indel_f1_mean:        float
    indel_precision_mean: float
    indel_recall_mean:    float
    runs_passing:         int
    runs_failing:         int


class ReproducibilityResultCreate(BaseModel):
    sample_id:    str = Field(..., min_length=1)
    run_ids:      str
    n_variants:   int = Field(..., ge=0)
    icc:          float = Field(..., ge=0, le=1)
    icc_ci_lower: float
    icc_ci_upper: float
    icc_p_value:  float
    icc_pass:     bool
    median_cv:    float
    p90_cv:       float
    overall_pass: bool
    alerts:       str | None = None


class ReproducibilityResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:           uuid.UUID
    sample_id:    str
    run_ids:      str
    n_variants:   int
    icc:          float
    icc_ci_lower: float
    icc_ci_upper: float
    icc_p_value:  float
    icc_pass:     bool
    median_cv:    float
    overall_pass: bool
    created_at:   datetime


class QualityAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:           uuid.UUID
    alert_type:   str
    severity:     str
    metric:       str | None
    variant_type: str | None
    value:        float | None
    threshold:    float | None
    message:      str
    resolved:     bool
    created_at:   datetime


class HealthResponse(BaseModel):
    status:    Literal["ok", "degraded"]
    database:  Literal["connected", "unreachable"]
    run_count: int
    version:   str = "1.0.0"
