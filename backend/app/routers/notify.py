from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user
from app.notify import send_email, send_wecom

router = APIRouter(prefix="/api/notify", tags=["通知配置"])


@router.get("", response_model=List[schemas.NotifyConfigOut])
async def list_configs(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    result = await db.execute(
        select(models.NotifyConfig).where(models.NotifyConfig.owner_id == current_user.id)
    )
    return result.scalars().all()


@router.post("", response_model=schemas.NotifyConfigOut)
async def create_config(
    data: schemas.NotifyConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    cfg = models.NotifyConfig(**data.model_dump(), owner_id=current_user.id)
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return cfg


@router.put("/{config_id}", response_model=schemas.NotifyConfigOut)
async def update_config(
    config_id: int,
    data: schemas.NotifyConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    cfg = await db.get(models.NotifyConfig, config_id)
    if not cfg or cfg.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="配置不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(cfg, k, v)
    await db.commit()
    await db.refresh(cfg)
    return cfg


@router.delete("/{config_id}")
async def delete_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    cfg = await db.get(models.NotifyConfig, config_id)
    if not cfg or cfg.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="配置不存在")
    await db.delete(cfg)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/{config_id}/test")
async def test_notify(
    config_id: int,
    data: schemas.TestNotifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    cfg = await db.get(models.NotifyConfig, config_id)
    if not cfg or cfg.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="配置不存在")

    if cfg.notify_type == "email":
        ok = send_email(
            cfg.smtp_server, cfg.smtp_port, cfg.sender_email,
            cfg.sender_password, cfg.receiver_email,
            "OCI Manager 测试通知", data.message,
        )
    elif cfg.notify_type == "wecom":
        ok = send_wecom(cfg.wecom_webhook, f"【OCI Manager 测试通知】\n{data.message}")
    else:
        raise HTTPException(status_code=400, detail="未知通知类型")

    return {"success": ok}
