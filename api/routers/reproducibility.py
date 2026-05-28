from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import ReproducibilityResult
from ..schemas import ReproducibilityResultCreate, ReproducibilityResultResponse

router = APIRouter()
get_db = None


@router.post("", response_model=ReproducibilityResultResponse, status_code=201)
async def create_reproducibility_result(payload: ReproducibilityResultCreate, db: AsyncSession = Depends(lambda: get_db())):
    result = ReproducibilityResult(**payload.model_dump())
    db.add(result)
    await db.flush()
    await db.refresh(result)
    return result


@router.get("", response_model=list[ReproducibilityResultResponse])
async def list_reproducibility_results(
    sample_id:    str | None = None,
    passing_only: bool = False,
    limit:  Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)]         = 0,
    db: AsyncSession = Depends(lambda: get_db()),
):
    q = select(ReproducibilityResult).order_by(ReproducibilityResult.created_at.desc())
    if sample_id:    q = q.where(ReproducibilityResult.sample_id == sample_id)
    if passing_only: q = q.where(ReproducibilityResult.overall_pass == True)
    return (await db.execute(q.offset(offset).limit(limit))).scalars().all()


@router.get("/{sample_id}/latest", response_model=ReproducibilityResultResponse)
async def get_latest(sample_id: str, db: AsyncSession = Depends(lambda: get_db())):
    row = (await db.execute(
        select(ReproducibilityResult)
        .where(ReproducibilityResult.sample_id == sample_id)
        .order_by(ReproducibilityResult.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, f"No reproducibility data for '{sample_id}'.")
    return row
