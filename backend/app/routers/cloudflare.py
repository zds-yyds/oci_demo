"""Cloudflare DNS 管理 — CF 配置 CRUD + DNS 记录 CRUD"""
import httpx
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app import models
from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cloudflare", tags=["Cloudflare DNS"])

CF_API_BASE = "https://api.cloudflare.com/client/v4"


# ── Schemas ───────────────────────────────────────────────────────────────────

class CfCfgCreate(BaseModel):
    name: str
    api_token: str
    zone_id: str
    domain: Optional[str] = None


class CfCfgUpdate(BaseModel):
    name: Optional[str] = None
    api_token: Optional[str] = None
    zone_id: Optional[str] = None
    domain: Optional[str] = None


class CfCfgOut(BaseModel):
    id: int
    name: str
    zone_id: str
    domain: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class DnsRecordCreate(BaseModel):
    cfg_id: int
    type: str           # A / AAAA / CNAME / MX / TXT / etc.
    name: str           # 记录名称，如 "www" 或 "@"
    content: str        # 记录值，如 IP 地址
    ttl: int = 1        # 1 = auto
    proxied: bool = False


class DnsRecordUpdate(BaseModel):
    cfg_id: int
    record_id: str
    type: str
    name: str
    content: str
    ttl: int = 1
    proxied: bool = False


class DnsRecordDelete(BaseModel):
    cfg_id: int
    record_ids: List[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cf_headers(api_token: str) -> dict:
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }


async def _get_cfg(cfg_id: int, db: AsyncSession, current_user: models.User) -> models.CloudflareCfg:
    cfg = await db.get(models.CloudflareCfg, cfg_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="CF 配置不存在")
    if not current_user.is_admin and cfg.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return cfg


# ── CF 配置 CRUD ──────────────────────────────────────────────────────────────

@router.get("/configs", response_model=List[CfCfgOut])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """列出当前用户的所有 CF 配置"""
    stmt = select(models.CloudflareCfg)
    if not current_user.is_admin:
        stmt = stmt.where(models.CloudflareCfg.owner_id == current_user.id)
    result = await db.execute(stmt.order_by(models.CloudflareCfg.created_at.desc()))
    cfgs = result.scalars().all()
    return [
        CfCfgOut(
            id=c.id, name=c.name, zone_id=c.zone_id, domain=c.domain,
            created_at=c.created_at.isoformat() if c.created_at else None,
        )
        for c in cfgs
    ]


@router.post("/configs", response_model=CfCfgOut)
async def create_config(
    data: CfCfgCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """添加 CF 配置"""
    # 验证 token 有效性
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{CF_API_BASE}/zones/{data.zone_id}",
            headers=_cf_headers(data.api_token),
        )
        if resp.status_code != 200:
            body = resp.json()
            errors = body.get("errors", [])
            msg = errors[0].get("message", "未知错误") if errors else "验证失败"
            raise HTTPException(status_code=400, detail=f"CF API 验证失败: {msg}")
        zone_info = resp.json().get("result", {})
        domain = zone_info.get("name", data.domain)

    cfg = models.CloudflareCfg(
        owner_id=current_user.id,
        name=data.name,
        api_token=data.api_token,
        zone_id=data.zone_id,
        domain=domain,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return CfCfgOut(
        id=cfg.id, name=cfg.name, zone_id=cfg.zone_id, domain=cfg.domain,
        created_at=cfg.created_at.isoformat() if cfg.created_at else None,
    )


@router.put("/configs/{cfg_id}", response_model=CfCfgOut)
async def update_config(
    cfg_id: int,
    data: CfCfgUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """更新 CF 配置"""
    cfg = await _get_cfg(cfg_id, db, current_user)
    if data.name is not None:
        cfg.name = data.name
    if data.api_token is not None:
        cfg.api_token = data.api_token
    if data.zone_id is not None:
        cfg.zone_id = data.zone_id
    if data.domain is not None:
        cfg.domain = data.domain
    await db.commit()
    await db.refresh(cfg)
    return CfCfgOut(
        id=cfg.id, name=cfg.name, zone_id=cfg.zone_id, domain=cfg.domain,
        created_at=cfg.created_at.isoformat() if cfg.created_at else None,
    )


@router.delete("/configs/{cfg_id}")
async def delete_config(
    cfg_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """删除 CF 配置"""
    cfg = await _get_cfg(cfg_id, db, current_user)
    await db.delete(cfg)
    await db.commit()
    return {"message": "删除成功"}


# ── DNS 记录 CRUD ─────────────────────────────────────────────────────────────

@router.get("/dns-records")
async def list_dns_records(
    cfg_id: int = Query(...),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    record_type: Optional[str] = Query(None, alias="type"),
    name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """列出 DNS 记录"""
    cfg = await _get_cfg(cfg_id, db, current_user)

    params = {"page": page, "per_page": per_page}
    if record_type:
        params["type"] = record_type
    if name:
        params["name"] = name

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{CF_API_BASE}/zones/{cfg.zone_id}/dns_records",
            headers=_cf_headers(cfg.api_token),
            params=params,
        )
    body = resp.json()
    if not body.get("success"):
        errors = body.get("errors", [])
        msg = errors[0].get("message", "未知错误") if errors else "请求失败"
        raise HTTPException(status_code=500, detail=f"获取 DNS 记录失败: {msg}")

    return {
        "records": body.get("result", []),
        "total": body.get("result_info", {}).get("total_count", 0),
        "page": page,
        "per_page": per_page,
    }


@router.post("/dns-records")
async def create_dns_record(
    data: DnsRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """添加 DNS 记录"""
    cfg = await _get_cfg(data.cfg_id, db, current_user)

    payload = {
        "type": data.type,
        "name": data.name,
        "content": data.content,
        "ttl": data.ttl,
        "proxied": data.proxied,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{CF_API_BASE}/zones/{cfg.zone_id}/dns_records",
            headers=_cf_headers(cfg.api_token),
            json=payload,
        )
    body = resp.json()
    if not body.get("success"):
        errors = body.get("errors", [])
        msg = errors[0].get("message", "未知错误") if errors else "创建失败"
        raise HTTPException(status_code=400, detail=f"添加 DNS 记录失败: {msg}")

    return {"message": "DNS 记录添加成功", "record": body.get("result")}


@router.put("/dns-records")
async def update_dns_record(
    data: DnsRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """更新 DNS 记录"""
    cfg = await _get_cfg(data.cfg_id, db, current_user)

    payload = {
        "type": data.type,
        "name": data.name,
        "content": data.content,
        "ttl": data.ttl,
        "proxied": data.proxied,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.put(
            f"{CF_API_BASE}/zones/{cfg.zone_id}/dns_records/{data.record_id}",
            headers=_cf_headers(cfg.api_token),
            json=payload,
        )
    body = resp.json()
    if not body.get("success"):
        errors = body.get("errors", [])
        msg = errors[0].get("message", "未知错误") if errors else "更新失败"
        raise HTTPException(status_code=400, detail=f"更新 DNS 记录失败: {msg}")

    return {"message": "DNS 记录更新成功", "record": body.get("result")}


@router.post("/dns-records/delete")
async def delete_dns_records(
    data: DnsRecordDelete,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """批量删除 DNS 记录"""
    cfg = await _get_cfg(data.cfg_id, db, current_user)

    results = []
    async with httpx.AsyncClient(timeout=15) as client:
        for record_id in data.record_ids:
            resp = await client.delete(
                f"{CF_API_BASE}/zones/{cfg.zone_id}/dns_records/{record_id}",
                headers=_cf_headers(cfg.api_token),
            )
            body = resp.json()
            if body.get("success"):
                results.append({"id": record_id, "status": "ok"})
            else:
                errors = body.get("errors", [])
                msg = errors[0].get("message", "未知错误") if errors else "删除失败"
                results.append({"id": record_id, "status": "failed", "error": msg})

    return {"message": f"已处理 {len(data.record_ids)} 条删除请求", "results": results}
