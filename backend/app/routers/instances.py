from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user
from app import oci_client

router = APIRouter(prefix="/api/instances", tags=["实例管理"])


async def _get_tenant(tenant_id: int, db: AsyncSession, current_user: models.User) -> models.Tenant:
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions)).where(models.Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
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
        result = oci_client.instance_action(tenant, instance_id, data.action, region=data.region)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"操作失败: {str(e)}")


@router.delete("/{tenant_id}/{instance_id}")
async def terminate_instance(
    tenant_id: int,
    instance_id: str,
    region: str = None,
    preserve_boot_volume: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """终止（删除）实例"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        result = oci_client.terminate_instance(
            tenant, instance_id, region=region, preserve_boot_volume=preserve_boot_volume
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除实例失败: {str(e)}")


@router.put("/{tenant_id}/{instance_id}/config")
async def update_instance_config(
    tenant_id: int,
    instance_id: str,
    data: schemas.InstanceConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """更改实例配置（shape / OCPU / 内存 / 名称）"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        result = oci_client.update_instance_config(
            tenant,
            instance_id,
            region=data.region,
            display_name=data.display_name,
            shape=data.shape,
            ocpus=data.ocpus,
            memory_in_gbs=data.memory_in_gbs,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更改实例配置失败: {str(e)}")
