import os
import json
import base64
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

# ── 加密工具函数 ─────────────────────────────────────────────────────────────

KDF_ITERATIONS = 600_000


def _derive_key(password: str, salt: bytes) -> bytes:
    """PBKDF2-SHA256 派生 256-bit 密钥"""
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, KDF_ITERATIONS)


def _encrypt_data(plaintext: bytes, password: str) -> dict:
    """AES-256-GCM 加密，返回包含 salt/nonce/密文的字典"""
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return {
        "version": 1,
        "kdf": "pbkdf2-sha256",
        "kdf_iterations": KDF_ITERATIONS,
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "data": base64.b64encode(ciphertext).decode(),
    }


def _decrypt_data(enc_obj: dict, password: str) -> bytes:
    """AES-256-GCM 解密"""
    salt = base64.b64decode(enc_obj["salt"])
    nonce = base64.b64decode(enc_obj["nonce"])
    ciphertext = base64.b64decode(enc_obj["data"])
    iterations = enc_obj.get("kdf_iterations", KDF_ITERATIONS)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)

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


@router.post("/export")
async def export_tenants(
    req: schemas.TenantExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """导出所有租户数据（含私钥），AES-256-GCM 加密"""
    if not req.password or len(req.password) < 6:
        raise HTTPException(status_code=400, detail="加密密码至少需要 6 个字符")

    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions))
    if not current_user.is_admin:
        stmt = stmt.where(models.Tenant.owner_id == current_user.id)
    result = await db.execute(stmt)
    tenants = result.scalars().all()

    # 构建导出数据
    export_data = []
    for t in tenants:
        export_data.append({
            "name": t.name,
            "user_ocid": t.user_ocid,
            "fingerprint": t.fingerprint,
            "tenancy_ocid": t.tenancy_ocid,
            "private_key": t.private_key,
            "region": [tr.region_identifier for tr in t.regions],
            "is_active": t.is_active,
        })

    plaintext = json.dumps(export_data, ensure_ascii=False).encode("utf-8")
    encrypted = _encrypt_data(plaintext, req.password)

    return Response(
        content=json.dumps(encrypted, ensure_ascii=False),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=oci_tenants_backup.enc"},
    )


@router.post("/import", response_model=schemas.TenantImportResult)
async def import_tenants(
    req: schemas.TenantImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """导入加密的租户备份文件"""
    if not req.password:
        raise HTTPException(status_code=400, detail="请输入解密密码")

    # 解析加密文件
    try:
        enc_obj = json.loads(base64.b64decode(req.file_content))
    except Exception:
        raise HTTPException(status_code=400, detail="文件格式无效，请确认是 .enc 备份文件")

    # 校验版本
    if enc_obj.get("version") != 1:
        raise HTTPException(status_code=400, detail="不支持的备份文件版本")

    # 解密
    try:
        plaintext = _decrypt_data(enc_obj, req.password)
    except Exception:
        raise HTTPException(status_code=400, detail="解密失败，密码错误或文件已损坏")

    # 解析 JSON
    try:
        tenant_list = json.loads(plaintext)
    except Exception:
        raise HTTPException(status_code=400, detail="解密后的数据格式无效")

    if not isinstance(tenant_list, list):
        raise HTTPException(status_code=400, detail="备份数据格式错误，应为数组")

    # 获取当前用户已有的 tenancy_ocid
    stmt = select(models.Tenant).where(models.Tenant.owner_id == current_user.id)
    result = await db.execute(stmt)
    existing_ocids = {t.tenancy_ocid for t in result.scalars().all()}

    created = 0
    skipped = 0
    skipped_names = []

    for item in tenant_list:
        tenancy_ocid = item.get("tenancy_ocid", "")
        if tenancy_ocid in existing_ocids:
            skipped += 1
            skipped_names.append(item.get("name", "未知"))
            continue

        # 创建新租户
        private_key = item.get("private_key", "")
        if not private_key:
            if not current_user.default_private_key:
                skipped += 1
                skipped_names.append(f"{item.get('name', '未知')}(无私钥)")
                continue
            private_key = current_user.default_private_key

        tenant = models.Tenant(
            name=item.get("name", "导入账户"),
            owner_id=current_user.id,
            user_ocid=item.get("user_ocid", ""),
            fingerprint=item.get("fingerprint", ""),
            tenancy_ocid=tenancy_ocid,
            private_key=private_key,
            is_active=item.get("is_active", True),
        )
        # 添加区域
        for r in item.get("region", []):
            tenant.regions.append(models.TenantRegion(region_identifier=r))
        db.add(tenant)
        existing_ocids.add(tenancy_ocid)
        created += 1

    await db.commit()
    return schemas.TenantImportResult(created=created, skipped=skipped, skipped_names=skipped_names)


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
