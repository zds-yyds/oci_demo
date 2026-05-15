from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/api/tenants", tags=["租户管理"])


def _tenant_to_out(tenant: models.Tenant) -> schemas.TenantOut:
    """将 Tenant ORM 对象转为输出 schema（含 region 列表）"""
    return schemas.TenantOut(
        id=tenant.id,
        name=tenant.name,
        user_ocid=tenant.user_ocid,
        fingerprint=tenant.fingerprint,
        tenancy_ocid=tenant.tenancy_ocid,
        region=tenant.region_list,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
    )


@router.get("", response_model=List[schemas.TenantOut])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions))
    if not current_user.is_admin:
        stmt = stmt.where(models.Tenant.owner_id == current_user.id)
    result = await db.execute(stmt)
    tenants = result.scalars().all()
    return [_tenant_to_out(t) for t in tenants]


@router.post("", response_model=schemas.TenantOut)
async def create_tenant(
    data: schemas.TenantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant_data = data.model_dump(exclude={"region"})
    # 如果未提供私钥，使用用户的默认私钥
    if not tenant_data.get("private_key"):
        if not current_user.default_private_key:
            raise HTTPException(status_code=400, detail="未提供私钥，且未设置默认私钥，请先在个人设置中配置默认私钥")
        tenant_data["private_key"] = current_user.default_private_key
    tenant = models.Tenant(**tenant_data, owner_id=current_user.id)
    # 添加区域关联
    for r in data.region:
        tenant.regions.append(models.TenantRegion(region_identifier=r))
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant, attribute_names=["regions"])
    return _tenant_to_out(tenant)


@router.get("/{tenant_id}", response_model=schemas.TenantOut)
async def get_tenant(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions)).where(models.Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return _tenant_to_out(tenant)


@router.put("/{tenant_id}", response_model=schemas.TenantOut)
async def update_tenant(
    tenant_id: int,
    data: schemas.TenantUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions)).where(models.Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")

    update_data = data.model_dump(exclude_none=True)
    # 处理区域更新
    if "region" in update_data:
        new_regions = update_data.pop("region")
        # 清除旧关联，添加新关联
        tenant.regions.clear()
        for r in new_regions:
            tenant.regions.append(models.TenantRegion(region_identifier=r))

    for k, v in update_data.items():
        setattr(tenant, k, v)
    await db.commit()
    await db.refresh(tenant, attribute_names=["regions"])
    return _tenant_to_out(tenant)


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
    """测试 OCI 连接是否正常（遍历所有区域）"""
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions)).where(models.Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    try:
        from app.oci_client import get_tenancy_name, test_all_regions
        name = get_tenancy_name(tenant)
        region_results = test_all_regions(tenant)
        return {"status": "ok", "tenancy_name": name, "regions": region_results}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
