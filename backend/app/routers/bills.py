from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from app.database import get_db
from app import models, schemas
from app.auth import get_current_user

router = APIRouter(prefix="/api/bills", tags=["账单管理"])


@router.get("/{tenant_id}/current")
async def get_current_bill(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """实时拉取当月账单"""
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions)).where(models.Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    try:
        import datetime
        import oci
        import tempfile, os
        from currency_converter import CurrencyConverter

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode="w")
        tmp.write(tenant.private_key)
        tmp.close()
        config = {
            "user": tenant.user_ocid,
            "fingerprint": tenant.fingerprint,
            "tenancy": tenant.tenancy_ocid,
            "region": tenant.region_list[0] if tenant.region_list else "us-ashburn-1",
            "key_file": tmp.name,
        }
        usage_client = oci.usage_api.UsageapiClient(config)
        now = datetime.datetime.utcnow()
        start_time = datetime.datetime(now.year, now.month, 1)
        end_time = datetime.datetime(now.year, now.month, now.day)
        usage_request = oci.usage_api.models.RequestSummarizedUsagesDetails(
            tenant_id=tenant.tenancy_ocid,
            time_usage_started=start_time,
            time_usage_ended=end_time,
            granularity="DAILY",
        )
        response = usage_client.request_summarized_usages(usage_request)
        os.unlink(tmp.name)

        c = CurrencyConverter()
        items = []
        total_cny = 0.0
        for bill in sorted(response.data.items, key=lambda x: x.time_usage_started):
            amount = bill.computed_amount or 0
            try:
                cny = round(c.convert(amount, bill.currency or "USD", "CNY"), 4)
            except Exception:
                cny = round(amount * 7.2, 4)
            total_cny += cny
            items.append({
                "start_time": str(bill.time_usage_started),
                "end_time": str(bill.time_usage_ended),
                "amount_cny": cny,
                "currency": bill.currency,
            })
        return {"items": items, "total_cny": round(total_cny, 4)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取账单失败: {str(e)}")


@router.get("/{tenant_id}/history", response_model=List[schemas.BillRecordOut])
async def get_bill_history(
    tenant_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    tenant = await db.get(models.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    result = await db.execute(
        select(models.BillRecord)
        .where(models.BillRecord.tenant_id == tenant_id)
        .order_by(models.BillRecord.start_time.desc())
    )
    return result.scalars().all()
