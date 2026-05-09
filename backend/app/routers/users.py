from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import hash_password, get_admin_user, get_current_user

router = APIRouter(prefix="/api/users", tags=["用户管理"])


def _user_to_out(user: models.User) -> schemas.UserOut:
    return schemas.UserOut(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        has_default_key=bool(user.default_private_key),
        created_at=user.created_at,
    )


@router.get("", response_model=List[schemas.UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_admin_user),
):
    result = await db.execute(select(models.User))
    return [_user_to_out(u) for u in result.scalars().all()]


@router.post("", response_model=schemas.UserOut)
async def create_user(
    data: schemas.UserCreate,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_admin_user),
):
    result = await db.execute(select(models.User).where(models.User.username == data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = models.User(
        username=data.username,
        hashed_password=hash_password(data.password),
        is_admin=data.is_admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _user_to_out(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_admin_user),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    await db.delete(user)
    await db.commit()
    return {"message": "删除成功"}


# ── 默认私钥 ──────────────────────────────────────────────────────────────────

@router.get("/me/default-key", response_model=schemas.DefaultKeyOut)
async def get_default_key(
    current_user: models.User = Depends(get_current_user),
):
    """查看当前用户是否设置了默认私钥"""
    has_key = bool(current_user.default_private_key)
    preview = None
    if has_key:
        # 只返回 -----BEGIN ... 那一行作为预览，不暴露私钥内容
        first_line = current_user.default_private_key.strip().splitlines()[0]
        preview = first_line
    return schemas.DefaultKeyOut(has_key=has_key, preview=preview)


@router.put("/me/default-key")
async def set_default_key(
    data: schemas.DefaultKeyUpdate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """设置或清除当前用户的默认私钥"""
    current_user.default_private_key = data.private_key.strip() or None
    await db.commit()
    return {"message": "保存成功", "has_key": bool(current_user.default_private_key)}


@router.get("/me/default-key/value")
async def get_default_key_value(
    current_user: models.User = Depends(get_current_user),
):
    """获取默认私钥完整内容（用于添加账户时预填）"""
    if not current_user.default_private_key:
        return {"private_key": ""}
    return {"private_key": current_user.default_private_key}
