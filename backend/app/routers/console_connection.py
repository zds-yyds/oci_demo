"""实例 VNC 控制台 — 通过 OCI Console Connection 创建 VNC 连接"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
from pydantic import BaseModel
from app.database import get_db
from app import models
from app.auth import get_current_user
from app import oci_client
import oci

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/console", tags=["VNC 控制台"])

_executor = ThreadPoolExecutor(max_workers=4)


# ── Schemas ───────────────────────────────────────────────────────────────────

class StartVncRequest(BaseModel):
    region: str
    instance_id: str


class VncConnectionResponse(BaseModel):
    connection_id: str
    vnc_connection_string: Optional[str] = None
    ssh_connection_string: Optional[str] = None
    private_key: Optional[str] = None
    message: str


class DeleteConnectionRequest(BaseModel):
    region: str
    connection_id: str


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


def _generate_ssh_keypair() -> dict:
    """生成 RSA 2048 SSH 密钥对"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    # 私钥 PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    # 公钥 OpenSSH 格式
    public_key = private_key.public_key()
    public_openssh = public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode("utf-8")

    return {
        "private_key": private_pem,
        "public_key_openssh": public_openssh,
    }


def _wait_for_active(compute_client, connection_id: str, max_attempts: int = 20, interval: float = 3.0):
    """轮询等待 Console Connection 变为 Active 状态"""
    for i in range(max_attempts):
        try:
            resp = compute_client.get_instance_console_connection(
                instance_console_connection_id=connection_id
            )
            conn = resp.data
            if conn.lifecycle_state == "ACTIVE":
                return conn
            logger.debug(f"[VNC] 等待连接激活... 状态: {conn.lifecycle_state} ({i+1}/{max_attempts})")
        except Exception as e:
            logger.warning(f"[VNC] 轮询连接状态失败: {e}")
        time.sleep(interval)
    return None


def _create_vnc_connection(tenant, region: str, instance_id: str) -> dict:
    """同步函数：创建 Console Connection 并等待激活"""
    config = oci_client.build_oci_config(tenant, region)
    compute = oci.core.ComputeClient(config)
    compartment_id = tenant.tenancy_ocid

    # 1. 检查并清理已有的 console connection
    try:
        existing = compute.list_instance_console_connections(
            compartment_id=compartment_id,
            instance_id=instance_id,
        ).data
        for conn in existing:
            if conn.lifecycle_state == "ACTIVE":
                # 已有活跃连接，直接返回
                return {
                    "connection_id": conn.id,
                    "vnc_connection_string": conn.vnc_connection_string,
                    "ssh_connection_string": conn.connection_string,
                    "private_key": None,
                    "message": "复用已有的 VNC 连接（无法提供私钥，如需新连接请先删除旧连接）",
                }
            elif conn.lifecycle_state not in ("DELETED", "DELETING"):
                # 清理非活跃的连接
                try:
                    compute.delete_instance_console_connection(
                        instance_console_connection_id=conn.id
                    )
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"[VNC] 检查已有连接失败: {e}")

    # 2. 生成 SSH 密钥对
    keypair = _generate_ssh_keypair()

    # 3. 创建 Console Connection
    create_details = oci.core.models.CreateInstanceConsoleConnectionDetails(
        instance_id=instance_id,
        public_key=keypair["public_key_openssh"],
    )
    resp = compute.create_instance_console_connection(
        create_instance_console_connection_details=create_details
    )
    connection_id = resp.data.id
    logger.info(f"[VNC] Console Connection 创建成功: {connection_id}")

    # 4. 等待连接激活
    conn = _wait_for_active(compute, connection_id)
    if not conn:
        return {
            "connection_id": connection_id,
            "vnc_connection_string": None,
            "ssh_connection_string": None,
            "private_key": keypair["private_key"],
            "message": "连接已创建但等待激活超时，请稍后刷新获取连接字符串",
        }

    return {
        "connection_id": connection_id,
        "vnc_connection_string": conn.vnc_connection_string,
        "ssh_connection_string": conn.connection_string,
        "private_key": keypair["private_key"],
        "message": "VNC 连接创建成功",
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{tenant_id}/start-vnc", response_model=VncConnectionResponse)
async def start_vnc(
    tenant_id: int,
    data: StartVncRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """创建实例 VNC 控制台连接"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            _create_vnc_connection,
            tenant,
            data.region,
            data.instance_id,
        )
        return VncConnectionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建 VNC 连接失败: {str(e)}")


@router.post("/{tenant_id}/delete-connection")
async def delete_connection(
    tenant_id: int,
    data: DeleteConnectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """删除 Console Connection"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        config = oci_client.build_oci_config(tenant, data.region)
        compute = oci.core.ComputeClient(config)
        compute.delete_instance_console_connection(
            instance_console_connection_id=data.connection_id
        )
        return {"message": "连接已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除连接失败: {str(e)}")
