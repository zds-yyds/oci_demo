"""流量统计 — 基于 OCI Monitoring API 的实时流量监控"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.database import get_db
from app import models
from app.auth import get_current_user
from app import oci_client
import oci

router = APIRouter(prefix="/api/traffic", tags=["流量统计"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TrafficDataRequest(BaseModel):
    region: str
    vnic_id: str
    begin_time: datetime
    end_time: datetime


class TrafficDataResponse(BaseModel):
    time: List[str]
    inbound: List[str]  # GB 格式
    outbound: List[str]


class RegionOption(BaseModel):
    label: str
    value: str


class InstanceOption(BaseModel):
    label: str
    value: str


class VnicOption(BaseModel):
    label: str
    value: str


class TrafficConditionResponse(BaseModel):
    region_options: List[RegionOption]


class FetchInstancesResponse(BaseModel):
    instances: List[InstanceOption]
    instance_count: int
    inbound_traffic: str  # 当月入站总流量
    outbound_traffic: str  # 当月出站总流量


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_bytes(byte_count: int, unit: str = "GB") -> str:
    """将字节数格式化为可读字符串"""
    if byte_count == 0:
        return "0 B"
    units = {"B": 0, "KB": 1, "MB": 2, "GB": 3, "TB": 4}
    divisor = 1024 ** units.get(unit, 3)
    value = byte_count / divisor
    return f"{value:.2f} {unit}"


def _format_bytes_value(byte_count: int) -> str:
    """将字节数格式化为 GB 数值字符串（用于图表）"""
    if byte_count == 0:
        return "0.00"
    value = byte_count / (1024 ** 3)
    return f"{value:.4f}"


async def _get_tenant(tenant_id: int, db: AsyncSession, current_user: models.User) -> models.Tenant:
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions)).where(models.Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return tenant


def _get_monitoring_client(tenant, region: str):
    config = oci_client.build_oci_config(tenant, region)
    return oci.monitoring.MonitoringClient(config), config


def _get_compute_client(tenant, region: str):
    config = oci_client.build_oci_config(tenant, region)
    return oci.core.ComputeClient(config), config


def _get_network_client(tenant, region: str):
    config = oci_client.build_oci_config(tenant, region)
    return oci.core.VirtualNetworkClient(config), config


def _query_traffic_metrics(monitoring_client, compartment_id: str, query: str,
                           start_time: datetime, end_time: datetime) -> List[dict]:
    """查询 OCI Monitoring 流量指标"""
    try:
        response = monitoring_client.summarize_metrics_data(
            compartment_id=compartment_id,
            summarize_metrics_data_details=oci.monitoring.models.SummarizeMetricsDataDetails(
                namespace="oci_vcn",
                query=query,
                start_time=start_time,
                end_time=end_time,
            ),
        )
        results = []
        for item in (response.data or []):
            for dp in (item.aggregated_datapoints or []):
                results.append({
                    "timestamp": dp.timestamp.strftime("%Y-%m-%d %H:%M"),
                    "value": int(dp.value),
                })
        # 按时间排序
        results.sort(key=lambda x: x["timestamp"])
        return results
    except Exception:
        return []


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{tenant_id}/conditions")
async def get_traffic_conditions(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取流量查询条件（可用区域列表）"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        # 使用 Identity API 获取订阅的区域
        identity_client, config = oci_client.get_identity_client(tenant)
        subscriptions = identity_client.list_region_subscriptions(
            tenancy_id=tenant.tenancy_ocid
        ).data

        region_options = [
            RegionOption(label=s.region_name, value=s.region_name)
            for s in subscriptions
        ]
        return TrafficConditionResponse(region_options=region_options)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取区域列表失败: {str(e)}")


@router.get("/{tenant_id}/instances")
async def fetch_instances(
    tenant_id: int,
    region: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取指定区域的实例列表及当月流量汇总"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        compute, config = _get_compute_client(tenant, region)
        network = oci.core.VirtualNetworkClient(config)
        monitoring = oci.monitoring.MonitoringClient(config)

        # 列出实例
        instances_resp = compute.list_instances(compartment_id=tenant.tenancy_ocid).data
        active_instances = [
            i for i in instances_resp
            if i.lifecycle_state not in ("TERMINATED", "TERMINATING")
        ]

        instance_options = [
            InstanceOption(label=i.display_name, value=i.id)
            for i in active_instances
        ]

        # 计算当月流量汇总
        now = datetime.utcnow()
        month_start = datetime(now.year, now.month, 1)
        total_in = 0
        total_out = 0

        for inst in active_instances:
            try:
                vnics_resp = compute.list_vnic_attachments(
                    compartment_id=tenant.tenancy_ocid, instance_id=inst.id
                ).data
                for va in vnics_resp:
                    if va.lifecycle_state != "ATTACHED":
                        continue
                    vnic_id = va.vnic_id
                    # 入站
                    in_query = f'VnicToNetworkBytes[1440m]{{resourceId = "{vnic_id}"}}.sum()'
                    in_data = _query_traffic_metrics(monitoring, tenant.tenancy_ocid, in_query, month_start, now)
                    total_in += sum(d["value"] for d in in_data)
                    # 出站
                    out_query = f'VnicFromNetworkBytes[1440m]{{resourceId = "{vnic_id}"}}.sum()'
                    out_data = _query_traffic_metrics(monitoring, tenant.tenancy_ocid, out_query, month_start, now)
                    total_out += sum(d["value"] for d in out_data)
            except Exception:
                continue

        return FetchInstancesResponse(
            instances=instance_options,
            instance_count=len(active_instances),
            inbound_traffic=_format_bytes(total_in),
            outbound_traffic=_format_bytes(total_out),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取实例列表失败: {str(e)}")


@router.get("/{tenant_id}/vnics")
async def fetch_vnics(
    tenant_id: int,
    region: str = Query(...),
    instance_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取实例的 VNIC 列表"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        compute, config = _get_compute_client(tenant, region)
        network = oci.core.VirtualNetworkClient(config)

        vnics_resp = compute.list_vnic_attachments(
            compartment_id=tenant.tenancy_ocid, instance_id=instance_id
        ).data

        vnic_options = []
        for va in vnics_resp:
            if va.lifecycle_state != "ATTACHED":
                continue
            try:
                vnic = network.get_vnic(vnic_id=va.vnic_id).data
                label = vnic.display_name or vnic.id
                if vnic.public_ip:
                    label += f" ({vnic.public_ip})"
                vnic_options.append(VnicOption(label=label, value=vnic.id))
            except Exception:
                vnic_options.append(VnicOption(label=va.vnic_id, value=va.vnic_id))

        return vnic_options
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 VNIC 列表失败: {str(e)}")


@router.post("/{tenant_id}/data")
async def get_traffic_data(
    tenant_id: int,
    data: TrafficDataRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取指定 VNIC 的流量数据（用于图表展示）"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        monitoring, config = _get_monitoring_client(tenant, data.region)

        # 入站查询: VnicToNetworkBytes
        in_query = f'VnicToNetworkBytes[5m]{{resourceId = "{data.vnic_id}"}}.sum()'
        in_data = _query_traffic_metrics(
            monitoring, tenant.tenancy_ocid, in_query, data.begin_time, data.end_time
        )

        # 出站查询: VnicFromNetworkBytes
        out_query = f'VnicFromNetworkBytes[5m]{{resourceId = "{data.vnic_id}"}}.sum()'
        out_data = _query_traffic_metrics(
            monitoring, tenant.tenancy_ocid, out_query, data.begin_time, data.end_time
        )

        # 对齐时间轴
        time_set = sorted(set(
            [d["timestamp"] for d in in_data] + [d["timestamp"] for d in out_data]
        ))
        in_map = {d["timestamp"]: d["value"] for d in in_data}
        out_map = {d["timestamp"]: d["value"] for d in out_data}

        return TrafficDataResponse(
            time=time_set,
            inbound=[_format_bytes_value(in_map.get(t, 0)) for t in time_set],
            outbound=[_format_bytes_value(out_map.get(t, 0)) for t in time_set],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取流量数据失败: {str(e)}")
