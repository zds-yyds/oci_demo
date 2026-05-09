from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/api/tenants", tags=["租户管理"])


@router.get("", response_model=List[schemas.TenantOut])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.is_admin:
        result = await db.execute(select(models.Tenant))
    else:
        result = await db.execute(
            select(models.Tenant).where(models.Tenant.owner_id == current_user.id)
        )
    return result.scalars().all()


@router.post("", response_model=schemas.TenantOut)
async def create_tenant(
    data: schemas.TenantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant = models.Tenant(**data.model_dump(), owner_id=current_user.id)
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.get("/{tenant_id}", response_model=schemas.TenantOut)
async def get_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant = await db.get(models.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return tenant


@router.put("/{tenant_id}", response_model=schemas.TenantOut)
async def update_tenant(
    tenant_id: int,
    data: schemas.TenantUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant = await db.get(models.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(tenant, k, v)
    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.delete("/{tenant_id}")
async def delete_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant = await db.get(models.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    await db.delete(tenant)
    await db.commit()
    return {"message": "删除成功"}


@router.get("/{tenant_id}/test")
async def test_tenant_connection(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """测试 OCI 连接是否正常"""
    tenant = await db.get(models.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    try:
        from app.oci_client import get_tenancy_name
        name = get_tenancy_name(tenant)
        return {"status": "ok", "tenancy_name": name}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
