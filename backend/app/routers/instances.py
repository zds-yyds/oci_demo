from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user
from app import oci_client

router = APIRouter(prefix="/api/instances", tags=["实例管理"])


async def _get_tenant(tenant_id: int, db: AsyncSession, current_user: models.User) -> models.Tenant:
    tenant = await db.get(models.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return tenant


@router.get("/{tenant_id}")
async def list_instances(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        instances = oci_client.list_instances(tenant)
        return instances
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取实例列表失败: {str(e)}")


@router.post("/{tenant_id}/{instance_id}/action")
async def do_instance_action(
    tenant_id: int,
    instance_id: str,
    data: schemas.InstanceAction,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant = await _get_tenant(tenant_id, db, current_user)
    allowed = {"START", "STOP", "RESET", "SOFTSTOP"}
    if data.action.upper() not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持的操作，允许: {allowed}")
    try:
        result = oci_client.instance_action(tenant, instance_id, data.action)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")
