"""SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class PipelineRun(Base):
    __tablename__ = "pipeline_run"

    id:           Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id:       Mapped[str]          = mapped_column(String(128), unique=True, nullable=False)
    sample_id:    Mapped[str]          = mapped_column(String(128), nullable=False, index=True)
    replicate:    Mapped[int]          = mapped_column(Integer, nullable=False)
    status:       Mapped[str]          = mapped_column(String(32), nullable=False, default="running")
    nextflow_run: Mapped[str | None]   = mapped_column(String(64))
    created_at:   Mapped[datetime]     = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    concordance_results: Mapped[list[ConcordanceResult]] = relationship(back_populates="run")
    quality_alerts:      Mapped[list[QualityAlert]]      = relationship(back_populates="run")


class ConcordanceResult(Base):
    __tablename__ = "concordance_result"
    __table_args__ = (UniqueConstraint("run_id", "variant_type", name="uq_concordance_run_vtype"),)

    id:              Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id:          Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_run.id"), nullable=False, index=True)
    variant_type:    Mapped[str]        = mapped_column(String(8),  nullable=False)
    true_positives:  Mapped[float]      = mapped_column(Float)
    false_positives: Mapped[float]      = mapped_column(Float)
    false_negatives: Mapped[float]      = mapped_column(Float)
    precision:       Mapped[float]      = mapped_column(Float, nullable=False)
    recall:          Mapped[float]      = mapped_column(Float, nullable=False)
    f1_score:        Mapped[float]      = mapped_column(Float, nullable=False)
    specificity:     Mapped[float]      = mapped_column(Float)
    cohen_kappa:     Mapped[float]      = mapped_column(Float)
    precision_pass:  Mapped[bool]       = mapped_column(Boolean, nullable=False)
    recall_pass:     Mapped[bool]       = mapped_column(Boolean, nullable=False)
    f1_pass:         Mapped[bool]       = mapped_column(Boolean, nullable=False)
    hapqy_file:      Mapped[str | None] = mapped_column(Text)
    created_at:      Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[PipelineRun] = relationship(back_populates="concordance_results")


class ReproducibilityResult(Base):
    __tablename__ = "reproducibility_result"

    id:           Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sample_id:    Mapped[str]        = mapped_column(String(128), nullable=False, index=True)
    run_ids:      Mapped[str]        = mapped_column(Text, nullable=False)
    n_variants:   Mapped[int]        = mapped_column(Integer)
    icc:          Mapped[float]      = mapped_column(Float, nullable=False)
    icc_ci_lower: Mapped[float]      = mapped_column(Float)
    icc_ci_upper: Mapped[float]      = mapped_column(Float)
    icc_p_value:  Mapped[float]      = mapped_column(Float)
    icc_pass:     Mapped[bool]       = mapped_column(Boolean, nullable=False)
    median_cv:    Mapped[float]      = mapped_column(Float)
    p90_cv:       Mapped[float]      = mapped_column(Float)
    overall_pass: Mapped[bool]       = mapped_column(Boolean, nullable=False)
    alerts:       Mapped[str | None] = mapped_column(Text)
    created_at:   Mapped[datetime]   = mapped_column(DateTime(timezone=True), server_default=func.now())


class QualityAlert(Base):
    __tablename__ = "quality_alert"

    id:           Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id:       Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_run.id"), nullable=True, index=True)
    alert_type:   Mapped[str]            = mapped_column(String(32), nullable=False)
    severity:     Mapped[str]            = mapped_column(String(16), nullable=False, default="warning")
    metric:       Mapped[str]            = mapped_column(String(64))
    variant_type: Mapped[str | None]     = mapped_column(String(8))
    value:        Mapped[float | None]   = mapped_column(Float)
    threshold:    Mapped[float | None]   = mapped_column(Float)
    message:      Mapped[str]            = mapped_column(Text, nullable=False)
    resolved:     Mapped[bool]           = mapped_column(Boolean, default=False)
    created_at:   Mapped[datetime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[PipelineRun | None] = relationship(back_populates="quality_alerts")


class WestgardViolationRecord(Base):
    __tablename__ = "westgard_violation"

    id:          Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id:      Mapped[str]       = mapped_column(String(128), nullable=False, index=True)
    metric:      Mapped[str]       = mapped_column(String(64),  nullable=False)
    rule:        Mapped[str]       = mapped_column(String(16),  nullable=False)
    value:       Mapped[float]     = mapped_column(Float,       nullable=False)
    is_warning:  Mapped[bool]      = mapped_column(Boolean,     nullable=False)
    description: Mapped[str]       = mapped_column(Text,        nullable=False)
    created_at:  Mapped[datetime]  = mapped_column(DateTime(timezone=True), server_default=func.now())
