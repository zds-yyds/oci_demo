from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    hashed_password = Column(String(256), nullable=False)
    is_admin = Column(Boolean, default=False)
    default_private_key = Column(Text, nullable=True)   # 用户默认 OCI 私钥
    created_at = Column(DateTime, default=datetime.utcnow)
    tenants = relationship("Tenant", back_populates="owner")


class Tenant(Base):
    """OCI 云账户租户配置"""
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # OCI config fields
    user_ocid = Column(String(256), nullable=False)
    fingerprint = Column(String(256), nullable=False)
    tenancy_ocid = Column(String(256), nullable=False)
    region = Column(String(64), nullable=False)
    private_key = Column(Text, nullable=False)   # PEM content
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="tenants")
    snipe_tasks = relationship("SnipeTask", back_populates="tenant")
    bill_records = relationship("BillRecord", back_populates="tenant")


class SnipeTask(Base):
    """抢机任务"""
    __tablename__ = "snipe_tasks"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    shape_name = Column(String(64), nullable=False)   # arm / amd
    instance_ocpus = Column(Integer, nullable=False)
    instance_memory_in_gbs = Column(Integer, nullable=False)
    boot_volume_size_in_gbs = Column(Integer, nullable=False)
    frequency = Column(Integer, default=10)
    ssh_public_key = Column(Text, nullable=True)
    status = Column(String(32), default="pending")  # pending/running/success/failed/stopped
    attempt_count = Column(Integer, default=0)
    result_instance_id = Column(String(256), nullable=True)
    result_ip = Column(String(64), nullable=True)
    log = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    tenant = relationship("Tenant", back_populates="snipe_tasks")


class BillRecord(Base):
    """账单记录"""
    __tablename__ = "bill_records"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    amount_cny = Column(Float, nullable=False)
    currency = Column(String(16), default="USD")
    created_at = Column(DateTime, default=datetime.utcnow)
    tenant = relationship("Tenant", back_populates="bill_records")


class NotifyConfig(Base):
    """通知配置（邮件 / 企业微信）"""
    __tablename__ = "notify_configs"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notify_type = Column(String(32), nullable=False)   # email / wecom
    # email fields
    smtp_server = Column(String(128), nullable=True)
    smtp_port = Column(Integer, nullable=True)
    sender_email = Column(String(128), nullable=True)
    sender_password = Column(String(256), nullable=True)
    receiver_email = Column(String(256), nullable=True)
    # wecom fields
    wecom_webhook = Column(String(512), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
