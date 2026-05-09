from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import models, schemas
from app.auth import verify_password, hash_password, create_access_token, get_current_user
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=schemas.Token)
async def login(data: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserOut)
async def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
async def change_password(
    data: dict,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    old_pwd = data.get("old_password", "")
    new_pwd = data.get("new_password", "")
    if not verify_password(old_pwd, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码错误")
    current_user.hashed_password = hash_password(new_pwd)
    await db.commit()
    return {"message": "密码修改成功"}
