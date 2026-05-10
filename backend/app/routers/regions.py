from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/api/regions", tags=["区域管理"])


@router.get("", response_model=List[schemas.RegionOut])
async def list_regions(
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """获取所有可用 OCI 区域"""
    result = await db.execute(select(models.Region).order_by(models.Region.identifier))
    return result.scalars().all()
