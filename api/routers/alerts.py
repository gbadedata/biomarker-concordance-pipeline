from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import QualityAlert
from ..schemas import QualityAlertResponse

router = APIRouter()
get_db = None


@router.get("", response_model=list[QualityAlertResponse])
async def list_alerts(
    unresolved_only: bool = True,
    severity: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: AsyncSession = Depends(lambda: get_db()),
):
    q = select(QualityAlert).order_by(QualityAlert.created_at.desc())
    if unresolved_only:
        q = q.where(not QualityAlert.resolved)
    if severity:
        q = q.where(QualityAlert.severity == severity)
    return (await db.execute(q.offset(offset).limit(limit))).scalars().all()


@router.patch("/{alert_id}/resolve", response_model=QualityAlertResponse)
async def resolve_alert(alert_id: str, db: AsyncSession = Depends(lambda: get_db())):
    alert = (await db.execute(
        select(QualityAlert).where(QualityAlert.id == uuid.UUID(alert_id))
    )).scalar_one_or_none()
    if not alert:
        raise HTTPException(404, "Alert not found.")
    alert.resolved = True
    await db.flush()
    await db.refresh(alert)
    return alert
