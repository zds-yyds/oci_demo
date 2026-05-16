"""配额查询 — 查询 OCI 服务配额和使用量（并发加速）"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app import models
from app.auth import get_current_user
from app import oci_client
import oci

router = APIRouter(prefix="/api/limits", tags=["配额查询"])

# 线程池：OCI SDK 是同步的，用线程池并发调用
_executor = ThreadPoolExecutor(max_workers=10)


# ── Schemas ───────────────────────────────────────────────────────────────────

class LimitItem(BaseModel):
    service_name: str
    limit_name: str
    description: Optional[str] = None
    scope_type: Optional[str] = None
    availability_domain: Optional[str] = None
    service_limit: Optional[int] = None
    used: Optional[int] = None
    available: Optional[int] = None


class LimitsResponse(BaseModel):
    total: int
    items: List[LimitItem]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_tenant(tenant_id: int, db: AsyncSession, current_user: models.User) -> models.Tenant:
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions)).where(models.Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return tenant


def _fetch_definition_details(limits_client, compartment_id: str, defn) -> List[LimitItem]:
    """同步函数：获取单个 definition 的 limit values 和 resource availability"""
    svc_name = defn.service_name
    limit_name = defn.name
    scope_type = defn.scope_type if defn.scope_type else "REGION"

    # 获取 limit values
    try:
        values_resp = limits_client.list_limit_values(
            compartment_id=compartment_id,
            service_name=svc_name,
            name=limit_name,
        )
        values = values_resp.data
    except Exception:
        values = []

    if not values:
        return [LimitItem(
            service_name=svc_name,
            limit_name=limit_name,
            description=defn.description,
            scope_type=str(scope_type),
        )]

    items = []
    for val in values:
        item = LimitItem(
            service_name=svc_name,
            limit_name=limit_name,
            description=defn.description,
            scope_type=str(scope_type),
            availability_domain=val.availability_domain,
            service_limit=val.value,
        )
        # 获取 resource availability
        try:
            avail_kwargs = {
                "compartment_id": compartment_id,
                "service_name": svc_name,
                "limit_name": limit_name,
            }
            if val.availability_domain:
                avail_kwargs["availability_domain"] = val.availability_domain
            avail_resp = limits_client.get_resource_availability(**avail_kwargs)
            item.used = avail_resp.data.used
            item.available = avail_resp.data.available
        except Exception:
            pass
        items.append(item)
    return items


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{tenant_id}/services")
async def list_services(
    tenant_id: int,
    region: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """列出可用的服务名称（用于下拉筛选）"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        config = oci_client.build_oci_config(tenant, region)
        limits_client = oci.limits.LimitsClient(config)

        services = []
        next_page = None
        while True:
            kwargs = {"compartment_id": tenant.tenancy_ocid}
            if next_page:
                kwargs["page"] = next_page
            resp = limits_client.list_services(**kwargs)
            for svc in resp.data:
                if svc.name:
                    services.append(svc.name)
            next_page = resp.next_page
            if not next_page:
                break

        return sorted(set(services))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务列表失败: {str(e)}")


@router.get("/{tenant_id}/query")
async def query_limits(
    tenant_id: int,
    region: str = Query(...),
    service_name: str = Query(..., description="服务名称，如 compute"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """查询指定服务的配额和使用量（并发加速）"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        config = oci_client.build_oci_config(tenant, region)
        limits_client = oci.limits.LimitsClient(config)
        compartment_id = tenant.tenancy_ocid

        # 1. 获取所有 limit definitions
        definitions = []
        next_page = None
        while True:
            kwargs = {
                "compartment_id": compartment_id,
                "service_name": service_name,
            }
            if next_page:
                kwargs["page"] = next_page
            resp = limits_client.list_limit_definitions(**kwargs)
            definitions.extend(resp.data)
            next_page = resp.next_page
            if not next_page:
                break

        # 2. 并发获取每个 definition 的详情（limit values + availability）
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                _executor,
                _fetch_definition_details,
                limits_client,
                compartment_id,
                defn,
            )
            for defn in definitions
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 3. 汇总结果
        items = []
        for result in results:
            if isinstance(result, Exception):
                continue
            items.extend(result)

        return LimitsResponse(total=len(items), items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询配额失败: {str(e)}")
