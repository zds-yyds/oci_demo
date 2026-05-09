from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type: str


class LoginRequest(BaseModel):
    username: str
    password: str


# ── User ──────────────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    has_default_key: bool = False   # 是否已设置默认私钥（不返回明文）
    created_at: datetime

    class Config:
        from_attributes = True


# ── Tenant ────────────────────────────────────────────────────────────────────
class TenantCreate(BaseModel):
    name: str
    user_ocid: str
    fingerprint: str
    tenancy_ocid: str
    region: str
    private_key: str   # PEM content


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    user_ocid: Optional[str] = None
    fingerprint: Optional[str] = None
    tenancy_ocid: Optional[str] = None
    region: Optional[str] = None
    private_key: Optional[str] = None
    is_active: Optional[bool] = None


class TenantOut(BaseModel):
    id: int
    name: str
    tenancy_ocid: str
    region: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── SnipeTask ─────────────────────────────────────────────────────────────────
class SnipeTaskCreate(BaseModel):
    tenant_id: int
    shape_name: str = "arm"
    instance_ocpus: int = 4
    instance_memory_in_gbs: int = 24
    boot_volume_size_in_gbs: int = 100
    frequency: int = 10
    ssh_public_key: Optional[str] = None


class SnipeTaskOut(BaseModel):
    id: int
    tenant_id: int
    shape_name: str
    instance_ocpus: int
    instance_memory_in_gbs: int
    boot_volume_size_in_gbs: int
    frequency: int
    status: str
    attempt_count: int
    result_instance_id: Optional[str]
    result_ip: Optional[str]
    log: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Instance control ──────────────────────────────────────────────────────────
class InstanceAction(BaseModel):
    action: str   # START / STOP / RESET / SOFTSTOP


class InstanceOut(BaseModel):
    id: str
    display_name: str
    lifecycle_state: str
    shape: str
    availability_domain: str
    public_ip: Optional[str]
    time_created: Optional[datetime]


# ── Bill ──────────────────────────────────────────────────────────────────────
class BillRecordOut(BaseModel):
    id: int
    tenant_id: int
    start_time: datetime
    end_time: datetime
    amount_cny: float
    currency: str

    class Config:
        from_attributes = True


# ── Notify ────────────────────────────────────────────────────────────────────
class NotifyConfigCreate(BaseModel):
    notify_type: str   # email / wecom
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    sender_email: Optional[str] = None
    sender_password: Optional[str] = None
    receiver_email: Optional[str] = None
    wecom_webhook: Optional[str] = None


class NotifyConfigOut(BaseModel):
    id: int
    notify_type: str
    smtp_server: Optional[str]
    smtp_port: Optional[int]
    sender_email: Optional[str]
    receiver_email: Optional[str]
    wecom_webhook: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class TestNotifyRequest(BaseModel):
    message: str = "这是一条测试消息"


# ── Default private key ───────────────────────────────────────────────────────
class DefaultKeyUpdate(BaseModel):
    private_key: str   # PEM content，传空字符串表示清除


class DefaultKeyOut(BaseModel):
    has_key: bool
    # 只返回前20个字符用于确认，不返回完整私钥
    preview: Optional[str] = None
