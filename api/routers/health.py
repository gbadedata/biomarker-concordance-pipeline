from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import HealthResponse

router = APIRouter()
get_db = None


@router.get("", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(lambda: get_db())):
    try:
        result = await db.execute(text("SELECT COUNT(*) FROM pipeline_run"))
        count  = result.scalar_one()
        return HealthResponse(status="ok", database="connected", run_count=count)
    except Exception:
        return HealthResponse(status="degraded", database="unreachable", run_count=0)
