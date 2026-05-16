"""VCN 管理 — 虚拟云网络列表、删除"""
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

router = APIRouter(prefix="/api/vcn", tags=["VCN 管理"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class VcnInfo(BaseModel):
    id: str
    display_name: str
    cidr_block: Optional[str] = None
    ipv6_cidr_blocks: Optional[List[str]] = None
    lifecycle_state: str
    time_created: Optional[str] = None
    default_security_list_id: Optional[str] = None


class DeleteVcnRequest(BaseModel):
    region: str
    vcn_ids: List[str]


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


def _delete_vcn_resources(network_client, compartment_id: str, vcn_id: str):
    """删除 VCN 前清理其下属资源（子网、网关、安全组、路由表规则）"""
    # 1. 清空默认路由表规则
    try:
        vcn = network_client.get_vcn(vcn_id=vcn_id).data
        if vcn.default_route_table_id:
            network_client.update_route_table(
                rt_id=vcn.default_route_table_id,
                update_route_table_details=oci.core.models.UpdateRouteTableDetails(
                    route_rules=[]
                ),
            )
    except Exception:
        pass

    # 2. 删除所有子网
    try:
        subnets = network_client.list_subnets(
            compartment_id=compartment_id, vcn_id=vcn_id
        ).data
        for subnet in subnets:
            try:
                network_client.delete_subnet(subnet_id=subnet.id)
            except Exception:
                pass
    except Exception:
        pass

    # 3. 删除所有 Internet 网关
    try:
        gateways = network_client.list_internet_gateways(
            compartment_id=compartment_id, vcn_id=vcn_id
        ).data
        for gw in gateways:
            try:
                network_client.delete_internet_gateway(ig_id=gw.id)
            except Exception:
                pass
    except Exception:
        pass

    # 4. 删除网络安全组
    try:
        nsgs = network_client.list_network_security_groups(
            compartment_id=compartment_id, vcn_id=vcn_id
        ).data
        for nsg in nsgs:
            try:
                network_client.delete_network_security_group(
                    network_security_group_id=nsg.id
                )
            except Exception:
                pass
    except Exception:
        pass

    # 5. 删除 VCN
    network_client.delete_vcn(vcn_id=vcn_id)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{tenant_id}")
async def list_vcns(
    tenant_id: int,
    region: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """列出指定区域的所有 VCN"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        config = oci_client.build_oci_config(tenant, region)
        network = oci.core.VirtualNetworkClient(config)

        vcns = network.list_vcns(compartment_id=tenant.tenancy_ocid).data
        result = []
        for v in vcns:
            if v.lifecycle_state == "TERMINATED":
                continue
            result.append(VcnInfo(
                id=v.id,
                display_name=v.display_name,
                cidr_block=v.cidr_block,
                ipv6_cidr_blocks=v.ipv6_cidr_blocks,
                lifecycle_state=v.lifecycle_state,
                time_created=v.time_created.isoformat() if v.time_created else None,
                default_security_list_id=v.default_security_list_id,
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 VCN 列表失败: {str(e)}")


@router.post("/{tenant_id}/delete")
async def delete_vcns(
    tenant_id: int,
    data: DeleteVcnRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """删除 VCN（会自动清理子网、网关等下属资源）"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        config = oci_client.build_oci_config(tenant, data.region)
        network = oci.core.VirtualNetworkClient(config)

        results = []
        for vcn_id in data.vcn_ids:
            try:
                _delete_vcn_resources(network, tenant.tenancy_ocid, vcn_id)
                results.append({"id": vcn_id, "status": "ok"})
            except Exception as e:
                results.append({"id": vcn_id, "status": "failed", "error": str(e)})

        return {"message": f"已处理 {len(data.vcn_ids)} 个 VCN 删除请求", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除 VCN 失败: {str(e)}")
