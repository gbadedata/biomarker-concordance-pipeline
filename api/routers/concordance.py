from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ConcordanceResult, PipelineRun
from ..schemas import (
    ConcordanceResultCreate,
    ConcordanceResultResponse,
    ConcordanceSummaryResponse,
)

router = APIRouter()
get_db = None


@router.post("", response_model=ConcordanceResultResponse, status_code=201)
async def create_concordance_result(
    payload: ConcordanceResultCreate,
    db: AsyncSession = Depends(lambda: get_db()),
):
    result = ConcordanceResult(**payload.model_dump())
    db.add(result)
    await db.flush()
    await db.refresh(result)
    return result


@router.get("", response_model=list[ConcordanceResultResponse])
async def list_concordance_results(
    variant_type: str | None = None,
    passing_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(lambda: get_db()),
):
    q = select(ConcordanceResult).order_by(ConcordanceResult.created_at.desc())
    if variant_type:
        q = q.where(ConcordanceResult.variant_type == variant_type.upper())
    if passing_only:
        q = q.where(ConcordanceResult.f1_pass)
    return (await db.execute(q.offset(offset).limit(limit))).scalars().all()


@router.get("/summary/{sample_id}", response_model=ConcordanceSummaryResponse)
async def concordance_summary(
    sample_id: str,
    db: AsyncSession = Depends(lambda: get_db()),
):
    q = (
        select(
            ConcordanceResult.variant_type,
            func.avg(ConcordanceResult.precision).label("prec_mean"),
            func.avg(ConcordanceResult.recall).label("rec_mean"),
            func.avg(ConcordanceResult.f1_score).label("f1_mean"),
            func.min(ConcordanceResult.f1_score).label("f1_min"),
            func.count(ConcordanceResult.id).label("n"),
        )
        .join(PipelineRun, ConcordanceResult.run_id == PipelineRun.id)
        .where(PipelineRun.sample_id == sample_id)
        .group_by(ConcordanceResult.variant_type)
    )
    rows = (await db.execute(q)).all()
    if not rows:
        raise HTTPException(404, f"No concordance data for '{sample_id}'.")

    snv   = next((r for r in rows if r.variant_type == "SNP"),   None)
    indel = next((r for r in rows if r.variant_type == "INDEL"), None)
    n     = max((snv.n if snv else 0), (indel.n if indel else 0))

    return ConcordanceSummaryResponse(
        sample_id=sample_id,
        n_runs=n,
        snv_f1_mean=round(snv.f1_mean, 4) if snv else 0.0,
        snv_f1_min=round(snv.f1_min, 4) if snv else 0.0,
        snv_precision_mean=round(snv.prec_mean, 4) if snv else 0.0,
        snv_recall_mean=round(snv.rec_mean, 4) if snv else 0.0,
        indel_f1_mean=round(indel.f1_mean, 4) if indel else 0.0,
        indel_precision_mean=round(indel.prec_mean, 4) if indel else 0.0,
        indel_recall_mean=round(indel.rec_mean, 4) if indel else 0.0,
        runs_passing=n,
        runs_failing=0,
    )
