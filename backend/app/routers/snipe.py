from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user
from app.config import settings
from app import snipe_worker

router = APIRouter(prefix="/api/snipe", tags=["抢机任务"])


async def _get_tenant(tenant_id: int, db: AsyncSession, current_user: models.User) -> models.Tenant:
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions)).where(models.Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return tenant


@router.get("", response_model=List[schemas.SnipeTaskOut])
async def list_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.is_admin:
        result = await db.execute(select(models.SnipeTask).order_by(models.SnipeTask.id.desc()))
    else:
        # Only tasks belonging to user's tenants
        result = await db.execute(
            select(models.SnipeTask)
            .join(models.Tenant)
            .where(models.Tenant.owner_id == current_user.id)
            .order_by(models.SnipeTask.id.desc())
        )
    return result.scalars().all()


@router.post("", response_model=schemas.SnipeTaskOut)
async def create_task(
    data: schemas.SnipeTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant = await _get_tenant(data.tenant_id, db, current_user)
    task = models.SnipeTask(**data.model_dump())
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.post("/{task_id}/start")
async def start_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = await db.get(models.SnipeTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    tenant = await _get_tenant(task.tenant_id, db, current_user)

    if snipe_worker.is_running(task_id):
        raise HTTPException(status_code=400, detail="任务已在运行中")

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
    }
    task.status = "running"
    task.log = ""
    task.attempt_count = 0
    await db.commit()

    snipe_worker.start_snipe_task(task_id, tenant_data, task_data, settings.database_url)
    return {"message": "任务已启动", "task_id": task_id}


@router.post("/{task_id}/stop")
async def stop_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = await db.get(models.SnipeTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    await _get_tenant(task.tenant_id, db, current_user)

    snipe_worker.stop_task(task_id)
    task.status = "stopped"
    await db.commit()
    return {"message": "停止信号已发送"}


@router.get("/{task_id}", response_model=schemas.SnipeTaskOut)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = await db.get(models.SnipeTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    await _get_tenant(task.tenant_id, db, current_user)
    return task


@router.delete("/{task_id}")
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = await db.get(models.SnipeTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    await _get_tenant(task.tenant_id, db, current_user)
    if snipe_worker.is_running(task_id):
        snipe_worker.stop_task(task_id)
    await db.delete(task)
    await db.commit()
    return {"message": "删除成功"}
