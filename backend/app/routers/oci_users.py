from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.database import get_db
from app import models
from app.auth import get_current_user
from app import oci_client
import oci

router = APIRouter(prefix="/api/oci-users", tags=["OCI用户管理"])


class CreateOCIUserRequest(BaseModel):
    email: str


async def _get_tenant(tenant_id: int, db: AsyncSession, current_user: models.User) -> models.Tenant:
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions)).where(models.Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return tenant


@router.get("/{tenant_id}")
async def list_oci_users(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """列出租户下所有 IAM 用户"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        identity, config = oci_client.get_identity_client(tenant)
        users = identity.list_users(compartment_id=config["tenancy"]).data
        result = []
        for user in users:
            result.append({
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "description": user.description,
                "lifecycle_state": user.lifecycle_state,
                "time_created": user.time_created.isoformat() if user.time_created else None,
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取用户列表失败: {str(e)}")


@router.post("/{tenant_id}")
async def create_oci_user(
    tenant_id: int,
    data: CreateOCIUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """创建 IAM 用户并添加到 Administrators 组"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        identity, config = oci_client.get_identity_client(tenant)
        compartment_id = config["tenancy"]

        # 创建用户
        create_user_details = oci.identity.models.CreateUserDetails(
            compartment_id=compartment_id,
            name=data.email,
            description="OCI Manager 创建",
            email=data.email,
        )
        user_response = identity.create_user(create_user_details)
        user_id = user_response.data.id

        # 查找 Administrators 组
        groups = identity.list_groups(compartment_id=compartment_id).data
        group_ocid = None
        for group in groups:
            if group.name == "Administrators":
                group_ocid = group.id
                break

        if not group_ocid:
            raise HTTPException(status_code=500, detail="未找到 Administrators 组")

        # 将用户添加到 Administrators 组
        add_user_details = oci.identity.models.AddUserToGroupDetails(
            group_id=group_ocid,
            user_id=user_id,
        )
        identity.add_user_to_group(add_user_details)

        return {
            "id": user_response.data.id,
            "name": user_response.data.name,
            "email": user_response.data.email,
            "lifecycle_state": user_response.data.lifecycle_state,
            "message": f"用户 {data.email} 创建成功并已添加到 Administrators 组",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建用户失败: {str(e)}")


@router.delete("/{tenant_id}/{user_ocid}")
async def delete_oci_user(
    tenant_id: int,
    user_ocid: str,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """删除 IAM 用户"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        identity, config = oci_client.get_identity_client(tenant)
        identity.delete_user(user_id=user_ocid)
        return {"message": "用户删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除用户失败: {str(e)}")
