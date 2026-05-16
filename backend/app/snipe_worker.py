"""抢机后台任务 Worker（每个任务独立线程）"""
import threading
import time
import datetime
import logging
import asyncio
import pytz
import oci
from typing import Dict

logger = logging.getLogger(__name__)

# 全局任务注册表 {task_id: threading.Thread}
_running_tasks: Dict[int, threading.Thread] = {}
_stop_flags: Dict[int, bool] = {}

ARM_SHAPE = "VM.Standard.A1.Flex"
AMD_SHAPE = "VM.Standard.E2.1.Micro"


def is_running(task_id: int) -> bool:
    t = _running_tasks.get(task_id)
    return t is not None and t.is_alive()


def stop_task(task_id: int):
    _stop_flags[task_id] = True


def _append_log(log_lines: list, msg: str):
    china_tz = pytz.timezone("Asia/Shanghai")
    ts = datetime.datetime.now(pytz.utc).astimezone(china_tz).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    log_lines.append(line)
    logger.info(line)


def _run_snipe(task_id: int, tenant_data: dict, task_data: dict, db_url: str):
    """在独立线程中执行抢机逻辑，完成后写回数据库"""
    import oci

    log_lines = []
    _stop_flags[task_id] = False

    shape_name = ARM_SHAPE if task_data["shape_name"] == "arm" else AMD_SHAPE
    ocpus = task_data["instance_ocpus"]
    memory = task_data["instance_memory_in_gbs"]
    boot_vol = task_data["boot_volume_size_in_gbs"]
    frequency = task_data["frequency"]
    ssh_key = task_data.get("ssh_public_key", "")

    # Build OCI config inline (no file needed)
    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode="w")
    tmp.write(tenant_data["private_key"])
    tmp.close()

    config = {
        "user": tenant_data["user_ocid"],
        "fingerprint": tenant_data["fingerprint"],
        "tenancy": tenant_data["tenancy_ocid"],
        "region": task_data.get("region") or tenant_data["region"].split(",")[0].strip(),
        "key_file": tmp.name,
    }

    try:
        # 设置请求超时（连接超时10s，读取超时60s），防止 API 调用无限挂起
        timeout = (10, 60)
        compute = oci.core.ComputeClient(config, timeout=timeout)
        identity = oci.identity.IdentityClient(config, timeout=timeout)
        network = oci.core.VirtualNetworkClient(config, timeout=timeout)
        compartment_id = tenant_data["tenancy_ocid"]

        # Get availability domains
        ads = [ad.name for ad in identity.list_availability_domains(compartment_id=compartment_id).data]
        _append_log(log_lines, f"可用域: {ads}")

        # Get image
        images = compute.list_images(compartment_id=compartment_id, shape=shape_name).data
        image_id = None
        preferred = ["Canonical-Ubuntu-20.04-2024.08.26-0", "Canonical-Ubuntu-20.04-aarch64-2024.08.26-0"]
        for img in images:
            if img.display_name in preferred:
                image_id = img.id
                break
        if not image_id and images:
            image_id = images[0].id
        if not image_id:
            _append_log(log_lines, "ERROR: 未找到合适镜像，任务终止")
            _update_task_db(db_url, task_id, "failed", "\n".join(log_lines))
            return

        _append_log(log_lines, f"使用镜像: {image_id}")

        # Get subnet
        subnets = network.list_subnets(compartment_id=compartment_id).data
        if not subnets:
            _append_log(log_lines, "ERROR: 未找到子网，任务终止")
            _update_task_db(db_url, task_id, "failed", "\n".join(log_lines))
            return
        subnet_id = subnets[0].id

        # Build launch request
        request = oci.core.models.LaunchInstanceDetails()
        request.compartment_id = compartment_id
        request.shape = shape_name
        if "flex" in shape_name.lower():
            request.shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=ocpus, memory_in_gbs=memory
            )
        request.create_vnic_details = oci.core.models.CreateVnicDetails(subnet_id=subnet_id)
        sd = oci.core.models.InstanceSourceViaImageDetails()
        sd.image_id = image_id
        sd.source_type = "image"
        if boot_vol > 0:
            sd.boot_volume_size_in_gbs = boot_vol
        request.source_details = sd
        request.is_pv_encryption_in_transit_enabled = True
        if ssh_key:
            request.metadata = {"ssh_authorized_keys": ssh_key}

        attempt = 0
        success = False
        result_instance_id = None
        result_ip = None

        while not _stop_flags.get(task_id, False):
            for ad in ads:
                if _stop_flags.get(task_id, False):
                    break
                request.availability_domain = ad
                attempt += 1
                _append_log(log_lines, f"第{attempt}次尝试 → {ad}")
                _update_task_db(db_url, task_id, "running", "\n".join(log_lines), attempt)
                try:
                    resp = compute.launch_instance(request)
                    if resp.status == 200:
                        inst = resp.data
                        result_instance_id = inst.id
                        _append_log(log_lines, f"实例创建成功！ID: {inst.id}")
                        time.sleep(60)
                        # Get public IP
                        try:
                            vnics = compute.list_vnic_attachments(
                                compartment_id=compartment_id, instance_id=inst.id
                            ).data
                            for va in vnics:
                                if va.lifecycle_state == "ATTACHED":
                                    vnic = network.get_vnic(vnic_id=va.vnic_id).data
                                    result_ip = vnic.public_ip
                                    break
                        except Exception:
                            pass
                        _append_log(log_lines, f"公网IP: {result_ip}")
                        success = True
                        break
                except Exception as e:
                    status_code = getattr(e, "status", None)
                    code = getattr(e, "code", None)
                    if status_code == 500:
                        _append_log(log_lines, f"容量不足({ad})，等待{frequency}s重试...")
                        time.sleep(frequency)
                    elif status_code == 429:
                        _append_log(log_lines, f"请求过快，等待{frequency * 2}s...")
                        time.sleep(frequency * 2)
                    elif status_code == 401:
                        _append_log(log_lines, f"API无权限: {code}，任务终止")
                        _update_task_db(db_url, task_id, "failed", "\n".join(log_lines), attempt)
                        return
                    else:
                        _append_log(log_lines, f"错误 {status_code}/{code}: {e}")
                        time.sleep(frequency)
            if success:
                break

        final_status = "success" if success else ("stopped" if _stop_flags.get(task_id) else "failed")
        _update_task_db(
            db_url, task_id, final_status, "\n".join(log_lines), attempt,
            result_instance_id, result_ip
        )

        # Notify
        _notify_result(db_url, task_id, tenant_data, final_status, result_ip, attempt)

    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass
        _running_tasks.pop(task_id, None)
        _stop_flags.pop(task_id, None)


def _update_task_db(db_url, task_id, status, log, attempt=0, instance_id=None, ip=None):
    """同步写回数据库（在线程中使用同步 SQLAlchemy）"""
    try:
        from sqlalchemy import create_engine, update
        from sqlalchemy.orm import Session
        from app.models import SnipeTask
        from app.config import settings
        # asyncpg → psycopg2 for sync usage in threads
        sync_url = settings.get_sync_url()
        engine = create_engine(sync_url)
        with Session(engine) as session:
            session.execute(
                update(SnipeTask)
                .where(SnipeTask.id == task_id)
                .values(
                    status=status,
                    log=log,
                    attempt_count=attempt,
                    result_instance_id=instance_id,
                    result_ip=ip,
                    updated_at=datetime.datetime.utcnow(),
                )
            )
            session.commit()
        engine.dispose()
    except Exception as e:
        logger.error(f"写回数据库失败: {e}")


def _notify_result(db_url, task_id, tenant_data, status, ip, attempt):
    """任务完成后发送通知"""
    try:
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session
        from app.models import NotifyConfig, Tenant
        from app.notify import send_email, send_wecom
        from app.config import settings

        sync_url = settings.get_sync_url()
        engine = create_engine(sync_url)
        with Session(engine) as session:
            tenant = session.get(Tenant, tenant_data["id"])
            if not tenant:
                return
            configs = session.execute(
                select(NotifyConfig).where(
                    NotifyConfig.owner_id == tenant.owner_id,
                    NotifyConfig.is_active == True,
                )
            ).scalars().all()

            if status == "success":
                subject = f"✅ 抢机成功！租户: {tenant_data['name']}"
                body = f"租户: {tenant_data['name']}\n任务ID: {task_id}\n公网IP: {ip}\n尝试次数: {attempt}"
            else:
                subject = f"❌ 抢机{status}！租户: {tenant_data['name']}"
                body = f"租户: {tenant_data['name']}\n任务ID: {task_id}\n状态: {status}\n尝试次数: {attempt}"

            for cfg in configs:
                if cfg.notify_type == "email" and cfg.sender_email:
                    send_email(cfg.smtp_server, cfg.smtp_port, cfg.sender_email,
                               cfg.sender_password, cfg.receiver_email, subject, body)
                elif cfg.notify_type == "wecom" and cfg.wecom_webhook:
                    send_wecom(cfg.wecom_webhook, f"【{subject}】\n{body}")
        engine.dispose()
    except Exception as e:
        logger.error(f"通知发送失败: {e}")


def start_snipe_task(task_id: int, tenant_data: dict, task_data: dict, db_url: str):
    if is_running(task_id):
        return False
    t = threading.Thread(
        target=_run_snipe,
        args=(task_id, tenant_data, task_data, db_url),
        daemon=True,
        name=f"snipe-{task_id}",
    )
    _running_tasks[task_id] = t
    t.start()
    return True


def resume_running_tasks():
    """
    服务启动时调用：恢复所有 status=running 的任务。
    Docker 重启后线程已丢失，需要重新启动。
    自动恢复的任务不发送通知。
    """
    try:
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import Session, selectinload
        from app.models import SnipeTask, Tenant
        from app.config import settings

        sync_url = settings.get_sync_url()
        engine = create_engine(sync_url)
        with Session(engine) as session:
            tasks = session.execute(
                select(SnipeTask).where(SnipeTask.status == "running")
            ).scalars().all()

            if not tasks:
                logger.info("无需恢复的抢机任务")
                engine.dispose()
                return

            logger.info(f"发现 {len(tasks)} 个需要恢复的抢机任务")

            for task in tasks:
                tenant = session.execute(
                    select(Tenant).options(selectinload(Tenant.regions)).where(Tenant.id == task.tenant_id)
                ).scalar_one_or_none()

                if not tenant:
                    logger.warning(f"任务 {task.id} 对应的租户不存在，标记为 failed")
                    task.status = "failed"
                    task.log = (task.log or "") + "\n[自动恢复] 租户已被删除，任务终止"
                    continue

                tenant_data = {
                    "id": tenant.id,
                    "name": tenant.name,
                    "user_ocid": tenant.user_ocid,
                    "fingerprint": tenant.fingerprint,
                    "tenancy_ocid": tenant.tenancy_ocid,
                    "region": tenant.region,
                    "private_key": tenant.private_key,
                    "owner_id": tenant.owner_id,
                }
                task_data = {
                    "shape_name": task.shape_name,
                    "instance_ocpus": task.instance_ocpus,
                    "instance_memory_in_gbs": task.instance_memory_in_gbs,
                    "boot_volume_size_in_gbs": task.boot_volume_size_in_gbs,
                    "frequency": task.frequency,
                    "ssh_public_key": task.ssh_public_key,
                    "region": task.region,
                }

                # 追加恢复日志
                task.log = (task.log or "") + "\n[自动恢复] 服务重启，任务自动继续..."
                session.commit()

                # 启动线程
                start_snipe_task(task.id, tenant_data, task_data, settings.database_url)
                logger.info(f"已恢复任务 {task.id} (租户: {tenant.name})")

            session.commit()
        engine.dispose()
    except Exception as e:
        logger.error(f"恢复抢机任务失败: {e}")
