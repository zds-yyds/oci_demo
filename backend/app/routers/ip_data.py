"""IP 数据管理 — IP 归属地查询 + 全球服务器地图 + CRUD + 从 OCI 加载"""
import threading
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
import httpx

from app.database import get_db, AsyncSessionLocal
from app import models
from app.auth import get_current_user
from app import oci_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ip-data", tags=["IP 数据管理"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class IpDataOut(BaseModel):
    id: int
    ip: str
    tenant_name: Optional[str] = None
    country: Optional[str] = None
    area: Optional[str] = None
    city: Optional[str] = None
    org: Optional[str] = None
    asn: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    ip_type: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IpDataPageResponse(BaseModel):
    items: List[IpDataOut]
    total: int


class AddIpRequest(BaseModel):
    ip: str


class RemoveIpRequest(BaseModel):
    ids: List[int]


class IpQueryResult(BaseModel):
    ip: str
    country: Optional[str] = None
    area: Optional[str] = None
    city: Optional[str] = None
    org: Optional[str] = None
    asn: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class MapPoint(BaseModel):
    ip: str
    lat: float
    lng: float
    tenant_name: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    org: Optional[str] = None


# ── IP-API helper ─────────────────────────────────────────────────────────────

def _query_ip_info(ip: str) -> dict:
    """调用 ip-api.com 查询 IP 归属地信息（中文）"""
    url = f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,lat,lon,org,as,query&lang=zh-CN"
    try:
        resp = httpx.get(url, timeout=10)
        data = resp.json()
        if data.get("status") != "success":
            return None
        return {
            "ip": data.get("query", ip),
            "country": data.get("country"),
            "area": data.get("regionName"),
            "city": data.get("city"),
            "org": data.get("org"),
            "asn": data.get("as"),
            "lat": data.get("lat"),
            "lng": data.get("lon"),
        }
    except Exception:
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/query")
async def query_ip(ip: str = Query(..., description="要查询的 IP 地址")):
    """查询单个 IP 的归属地信息（不入库）"""
    result = _query_ip_info(ip)
    if not result:
        raise HTTPException(status_code=400, detail=f"IP 查询失败: {ip}")
    return IpQueryResult(**result)


@router.get("/map")
async def get_map_data(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取全球服务器地图数据（所有有经纬度的 IP 记录）"""
    result = await db.execute(
        select(models.IpData).where(
            models.IpData.lat.isnot(None),
            models.IpData.lng.isnot(None),
        )
    )
    records = result.scalars().all()
    points = [
        MapPoint(
            ip=r.ip,
            lat=r.lat,
            lng=r.lng,
            tenant_name=r.tenant_name,
            country=r.country,
            city=r.city,
            org=r.org,
        )
        for r in records
    ]
    return points


@router.get("/list")
async def list_ip_data(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """分页查询 IP 数据"""
    query = select(models.IpData)
    count_query = select(func.count(models.IpData.id))

    if keyword:
        like_pattern = f"%{keyword}%"
        filter_cond = (
            models.IpData.ip.ilike(like_pattern) |
            models.IpData.country.ilike(like_pattern) |
            models.IpData.city.ilike(like_pattern) |
            models.IpData.org.ilike(like_pattern) |
            models.IpData.asn.ilike(like_pattern)
        )
        query = query.where(filter_cond)
        count_query = count_query.where(filter_cond)

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(models.IpData.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return IpDataPageResponse(
        items=[IpDataOut.model_validate(item) for item in items],
        total=total,
    )


@router.post("/add")
async def add_ip_data(
    data: AddIpRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """添加 IP 数据（自动查询归属地）"""
    info = _query_ip_info(data.ip)
    if not info:
        raise HTTPException(status_code=400, detail=f"IP 查询失败: {data.ip}")

    # 如果已存在则更新
    existing = await db.execute(
        select(models.IpData).where(models.IpData.ip == info["ip"])
    )
    record = existing.scalar_one_or_none()

    if record:
        record.country = info["country"]
        record.area = info["area"]
        record.city = info["city"]
        record.org = info["org"]
        record.asn = info["asn"]
        record.lat = info["lat"]
        record.lng = info["lng"]
    else:
        record = models.IpData(
            ip=info["ip"],
            country=info["country"],
            area=info["area"],
            city=info["city"],
            org=info["org"],
            asn=info["asn"],
            lat=info["lat"],
            lng=info["lng"],
        )
        db.add(record)

    await db.commit()
    return {"message": "IP 数据添加成功", "ip": info["ip"]}


@router.post("/refresh/{ip_data_id}")
async def refresh_ip_data(
    ip_data_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """刷新（重新查询）某条 IP 记录的归属地信息"""
    record = await db.get(models.IpData, ip_data_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    info = _query_ip_info(record.ip)
    if not info:
        raise HTTPException(status_code=400, detail=f"IP 查询失败: {record.ip}")

    record.country = info["country"]
    record.area = info["area"]
    record.city = info["city"]
    record.org = info["org"]
    record.asn = info["asn"]
    record.lat = info["lat"]
    record.lng = info["lng"]
    await db.commit()
    return {"message": "IP 数据刷新成功"}


@router.post("/remove")
async def remove_ip_data(
    data: RemoveIpRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """批量删除 IP 数据"""
    await db.execute(
        delete(models.IpData).where(models.IpData.id.in_(data.ids))
    )
    await db.commit()
    return {"message": f"已删除 {len(data.ids)} 条记录"}


@router.post("/load-from-oci")
async def load_from_oci(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """从所有 OCI 租户加载实例公网 IP 数据（异步执行）"""
    # 获取当前用户的所有租户
    if current_user.is_admin:
        result = await db.execute(
            select(models.Tenant).options(selectinload(models.Tenant.regions))
        )
    else:
        result = await db.execute(
            select(models.Tenant)
            .options(selectinload(models.Tenant.regions))
            .where(models.Tenant.owner_id == current_user.id)
        )
    tenants = result.scalars().all()

    if not tenants:
        raise HTTPException(status_code=400, detail="无可用租户")

    # 收集租户数据用于后台线程
    tenant_data_list = []
    for t in tenants:
        tenant_data_list.append({
            "id": t.id,
            "name": t.name,
            "user_ocid": t.user_ocid,
            "fingerprint": t.fingerprint,
            "tenancy_ocid": t.tenancy_ocid,
            "private_key": t.private_key,
            "regions": [tr.region_identifier for tr in t.regions],
        })

    # 异步执行
    from app.config import settings
    thread = threading.Thread(
        target=_load_oci_ips_worker,
        args=(tenant_data_list, settings.get_sync_url()),
        daemon=True,
    )
    thread.start()

    return {"message": f"已提交 IP 数据同步任务，正在从 {len(tenants)} 个租户加载..."}


# ── Background worker ─────────────────────────────────────────────────────────

def _load_oci_ips_worker(tenant_data_list: list, sync_db_url: str):
    """后台线程：遍历所有租户实例，收集公网 IP 并查询归属地"""
    import time
    from sqlalchemy import create_engine, select as sync_select, delete as sync_delete
    from sqlalchemy.orm import Session

    try:
        engine = create_engine(sync_db_url)

        # 清除旧的 OCI 类型 IP 数据
        with Session(engine) as session:
            session.execute(
                sync_delete(models.IpData).where(models.IpData.ip_type == "oracle")
            )
            session.commit()

        logger.info("[IP同步] 开始从 OCI 加载 IP 数据...")

        for tenant_data in tenant_data_list:
            for region in tenant_data["regions"]:
                try:
                    config = {
                        "user": tenant_data["user_ocid"],
                        "fingerprint": tenant_data["fingerprint"],
                        "tenancy": tenant_data["tenancy_ocid"],
                        "region": region,
                        "key_content": tenant_data["private_key"],
                    }
                    import oci
                    compute = oci.core.ComputeClient(config)
                    network = oci.core.VirtualNetworkClient(config)
                    identity = oci.identity.IdentityClient(config)
                    root_compartment_id = tenant_data["tenancy_ocid"]

                    # 遍历所有 compartment（根 + 子区间）
                    compartment_ids = [root_compartment_id]
                    try:
                        sub_compartments = identity.list_compartments(
                            compartment_id=root_compartment_id,
                            compartment_id_in_subtree=True,
                            lifecycle_state="ACTIVE",
                        ).data
                        for c in sub_compartments:
                            compartment_ids.append(c.id)
                    except Exception:
                        pass

                    for compartment_id in compartment_ids:
                        try:
                            instances = compute.list_instances(compartment_id=compartment_id).data
                        except Exception:
                            continue
                        for inst in instances:
                            if inst.lifecycle_state in ("TERMINATED", "TERMINATING"):
                                continue
                            try:
                                vnics = compute.list_vnic_attachments(
                                    compartment_id=compartment_id, instance_id=inst.id
                                ).data
                                for va in vnics:
                                    if va.lifecycle_state != "ATTACHED":
                                        continue
                                    vnic = network.get_vnic(vnic_id=va.vnic_id).data
                                    if vnic.public_ip:
                                        # 查询 IP 归属地
                                        info = _query_ip_info(vnic.public_ip)
                                        if info:
                                            with Session(engine) as session:
                                                ip_record = models.IpData(
                                                    ip=info["ip"],
                                                    country=info["country"],
                                                    area=info["area"],
                                                    city=info["city"],
                                                    org=info["org"],
                                                    asn=info["asn"],
                                                    lat=info["lat"],
                                                    lng=info["lng"],
                                                    ip_type="oracle",
                                                    tenant_name=tenant_data["name"],
                                                )
                                                session.add(ip_record)
                                                session.commit()
                                            logger.info(f"[IP同步] {tenant_data['name']}/{region}: {vnic.public_ip} → {info['city']}, {info['country']}")
                                        # ip-api.com 免费版限流 45 req/min
                                        time.sleep(1.5)
                            except Exception as e:
                                logger.debug(f"[IP同步] 获取实例 VNIC 失败: {e}")
                                continue
                except Exception as e:
                    logger.warning(f"[IP同步] 租户 {tenant_data['name']}/{region} 失败: {e}")
                    continue

        logger.info("[IP同步] 任务完成")
        engine.dispose()
    except Exception as e:
        logger.error(f"[IP同步] 任务异常: {e}", exc_info=True)
