from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/api/ssh-credentials", tags=["SSH凭据"])


@router.get("", response_model=List[schemas.SSHCredentialOut])
async def list_credentials(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    result = await db.execute(
        select(models.SSHCredential).where(models.SSHCredential.owner_id == current_user.id)
    )
    creds = result.scalars().all()
    return [
        schemas.SSHCredentialOut(
            id=c.id,
            label=c.label,
            host=c.host,
            port=c.port,
            username=c.username,
            auth_type=c.auth_type,
            has_password=bool(c.password),
            has_key=bool(c.private_key),
            created_at=c.created_at,
        )
        for c in creds
    ]


@router.post("", response_model=schemas.SSHCredentialOut)
async def create_credential(
    data: schemas.SSHCredentialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    cred = models.SSHCredential(**data.model_dump(), owner_id=current_user.id)
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return schemas.SSHCredentialOut(
        id=cred.id,
        label=cred.label,
        host=cred.host,
        port=cred.port,
        username=cred.username,
        auth_type=cred.auth_type,
        has_password=bool(cred.password),
        has_key=bool(cred.private_key),
        created_at=cred.created_at,
    )


@router.put("/{cred_id}", response_model=schemas.SSHCredentialOut)
async def update_credential(
    cred_id: int,
    data: schemas.SSHCredentialUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    cred = await db.get(models.SSHCredential, cred_id)
    if not cred or cred.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="凭据不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(cred, k, v)
    await db.commit()
    await db.refresh(cred)
    return schemas.SSHCredentialOut(
        id=cred.id,
        label=cred.label,
        host=cred.host,
        port=cred.port,
        username=cred.username,
        auth_type=cred.auth_type,
        has_password=bool(cred.password),
        has_key=bool(cred.private_key),
        created_at=cred.created_at,
    )


@router.delete("/{cred_id}")
async def delete_credential(
    cred_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    cred = await db.get(models.SSHCredential, cred_id)
    if not cred or cred.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="凭据不存在")
    await db.delete(cred)
    await db.commit()
    return {"message": "删除成功"}


@router.get("/{cred_id}/secret")
async def get_credential_secret(
    cred_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """获取凭据的完整信息（含密码/私钥），用于 SSH 连接"""
    cred = await db.get(models.SSHCredential, cred_id)
    if not cred or cred.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="凭据不存在")
    return {
        "host": cred.host,
        "port": cred.port,
        "username": cred.username,
        "auth_type": cred.auth_type,
        "password": cred.password or "",
        "private_key": cred.private_key or "",
    }
