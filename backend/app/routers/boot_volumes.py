"""引导卷管理 — 列表、终止、更新配置"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.database import get_db
from app import models
from app.auth import get_current_user
from app import oci_client
import oci

router = APIRouter(prefix="/api/boot-volumes", tags=["引导卷管理"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class BootVolumeInfo(BaseModel):
    id: str
    display_name: str
    availability_domain: str
    size_in_gbs: int
    vpus_per_gb: int
    lifecycle_state: str
    region: Optional[str] = None
    time_created: Optional[str] = None
    instance_ocpus: Optional[float] = None
    instance_memory_in_gbs: Optional[float] = None
    instance_shape: Optional[str] = None


class UpdateBootVolumeRequest(BaseModel):
    region: str
    boot_volume_id: str
    size_in_gbs: int  # 新大小（GB）
    vpus_per_gb: int = 10  # 性能单位 [10, 120]


class TerminateBootVolumeRequest(BaseModel):
    region: str
    boot_volume_ids: List[str]


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


# ── Endpoints ─────────────────────────────────────────────────────────────────

def _fetch_boot_volumes_for_region(tenant, region: str) -> list:
    """获取单个区域的所有引导卷（含关联实例配置，遍历所有 compartment）"""
    try:
        config = oci_client.build_oci_config(tenant, region)
        block_storage = oci.core.BlockstorageClient(config)
        identity = oci.identity.IdentityClient(config)
        compute = oci.core.ComputeClient(config)

        ads = identity.list_availability_domains(compartment_id=tenant.tenancy_ocid).data

        # 遍历所有 compartment（与实例管理保持一致）
        compartment_ids = oci_client.list_all_compartments(tenant, region)

        # 建立 boot_volume_id -> instance_id 映射（覆盖所有 compartment）
        bv_to_instance = {}
        try:
            for compartment_id in compartment_ids:
                for ad in ads:
                    try:
                        attachments = compute.list_boot_volume_attachments(
                            availability_domain=ad.name,
                            compartment_id=compartment_id,
                        ).data
                        for att in attachments:
                            if att.lifecycle_state == "ATTACHED":
                                bv_to_instance[att.boot_volume_id] = att.instance_id
                    except Exception:
                        continue
        except Exception:
            pass

        instance_cache = {}
        result = []
        for compartment_id in compartment_ids:
            for ad in ads:
                try:
                    volumes = block_storage.list_boot_volumes(
                        availability_domain=ad.name,
                        compartment_id=compartment_id,
                    ).data
                    for vol in volumes:
                        if vol.lifecycle_state == "TERMINATED":
                            continue

                        ocpus = None
                        memory_in_gbs = None
                        shape = None

                        inst_id = bv_to_instance.get(vol.id)
                        if inst_id:
                            if inst_id not in instance_cache:
                                try:
                                    inst = compute.get_instance(instance_id=inst_id).data
                                    instance_cache[inst_id] = inst
                                except Exception:
                                    instance_cache[inst_id] = None
                            inst = instance_cache.get(inst_id)
                            if inst and inst.shape_config:
                                ocpus = inst.shape_config.ocpus
                                memory_in_gbs = inst.shape_config.memory_in_gbs
                                shape = inst.shape

                        result.append(BootVolumeInfo(
                            id=vol.id,
                            display_name=vol.display_name,
                            availability_domain=vol.availability_domain,
                            size_in_gbs=vol.size_in_gbs,
                            vpus_per_gb=vol.vpus_per_gb,
                            lifecycle_state=vol.lifecycle_state,
                            region=region,
                            time_created=vol.time_created.isoformat() if vol.time_created else None,
                            instance_ocpus=ocpus,
                            instance_memory_in_gbs=memory_in_gbs,
                            instance_shape=shape,
                        ))
                except Exception:
                    continue
        return result
    except Exception:
        return []


@router.get("/{tenant_id}")
async def list_boot_volumes(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """列出租户下所有区域的引导卷（并发加速）"""
    tenant = await _get_tenant(tenant_id, db, current_user)

    # 获取租户的所有区域
    regions = []
    if hasattr(tenant, 'region_list') and tenant.region_list:
        regions = tenant.region_list
    elif hasattr(tenant, 'region') and tenant.region:
        regions = [r.strip() for r in tenant.region.split(",") if r.strip()]

    if not regions:
        return []

    result = []
    with ThreadPoolExecutor(max_workers=len(regions)) as executor:
        futures = [executor.submit(_fetch_boot_volumes_for_region, tenant, r) for r in regions]
        for future in as_completed(futures):
            try:
                result.extend(future.result())
            except Exception:
                continue

    return result


@router.post("/{tenant_id}/terminate")
async def terminate_boot_volumes(
    tenant_id: int,
    data: TerminateBootVolumeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """终止（删除）引导卷"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        config = oci_client.build_oci_config(tenant, data.region)
        block_storage = oci.core.BlockstorageClient(config)

        results = []
        for bv_id in data.boot_volume_ids:
            try:
                block_storage.delete_boot_volume(boot_volume_id=bv_id)
                results.append({"id": bv_id, "status": "ok"})
            except Exception as e:
                results.append({"id": bv_id, "status": "failed", "error": str(e)})

        return {"message": f"已发送终止指令 {len(data.boot_volume_ids)} 个引导卷", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"终止引导卷失败: {str(e)}")


@router.put("/{tenant_id}/update")
async def update_boot_volume(
    tenant_id: int,
    data: UpdateBootVolumeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """更新引导卷配置（大小、性能）"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        config = oci_client.build_oci_config(tenant, data.region)
        block_storage = oci.core.BlockstorageClient(config)

        update_details = oci.core.models.UpdateBootVolumeDetails(
            size_in_gbs=data.size_in_gbs if data.size_in_gbs != 50 else None,
            vpus_per_gb=data.vpus_per_gb,
        )

        block_storage.update_boot_volume(
            boot_volume_id=data.boot_volume_id,
            update_boot_volume_details=update_details,
        )
        return {"message": "引导卷配置更新成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新引导卷配置失败: {str(e)}")
