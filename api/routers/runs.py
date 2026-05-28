from __future__ import annotations
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import PipelineRun
from ..schemas import PipelineRunCreate, PipelineRunResponse, PipelineRunUpdate

router = APIRouter()

@router.post("", response_model=PipelineRunResponse, status_code=201)
async def create_run(payload: PipelineRunCreate, db: AsyncSession = Depends(get_db)):
    existing = (await db.execute(select(PipelineRun).where(PipelineRun.run_id == payload.run_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, f"Run '{payload.run_id}' already exists.")
    run = PipelineRun(**payload.model_dump())
    db.add(run)
    await db.flush()
    await db.refresh(run)
    return run

@router.get("", response_model=list[PipelineRunResponse])
async def list_runs(
    sample_id: str | None = None, status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(PipelineRun).order_by(PipelineRun.created_at.desc())
    if sample_id: q = q.where(PipelineRun.sample_id == sample_id)
    if status: q = q.where(PipelineRun.status == status)
    return (await db.execute(q.offset(offset).limit(limit))).scalars().all()

@router.get("/{run_id}", response_model=PipelineRunResponse)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(select(PipelineRun).where(PipelineRun.run_id == run_id))).scalar_one_or_none()
    if not run: raise HTTPException(404, f"Run '{run_id}' not found.")
    return run

@router.patch("/{run_id}", response_model=PipelineRunResponse)
async def update_run(run_id: str, payload: PipelineRunUpdate, db: AsyncSession = Depends(get_db)):
    run = (await db.execute(select(PipelineRun).where(PipelineRun.run_id == run_id))).scalar_one_or_none()
    if not run: raise HTTPException(404, f"Run '{run_id}' not found.")
    for k, v in payload.model_dump(exclude_unset=True).items(): setattr(run, k, v)
    await db.flush()
    await db.refresh(run)
    return run
