from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_admin_user
from app.database import get_db
from app.models import (
    ChannelStatus,
    ModelPricing,
    RechargeOrder,
    RedeemCode,
    Transaction,
    UpstreamChannel,
    UsageLog,
    User,
    UserRole,
)
from app.schemas import (
    ChannelCreate,
    ChannelOut,
    ChannelUpdate,
    DashboardStats,
    ModelPricingCreate,
    ModelPricingOut,
    ModelPricingUpdate,
    RechargeRequest,
    RedeemCodeCreate,
    RedeemCodeOut,
    UserOut,
)
from app.services.billing import ensure_pricing_for_models, recharge_balance

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.get("/stats", response_model=DashboardStats)
async def stats(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    balance = (await db.execute(select(func.sum(User.balance)))).scalar() or 0.0
    today_req = (
        await db.execute(select(func.count(UsageLog.id)).where(UsageLog.created_at >= today))
    ).scalar() or 0
    today_rev = (
        await db.execute(select(func.sum(UsageLog.cost)).where(UsageLog.created_at >= today, UsageLog.status == "success"))
    ).scalar() or 0.0
    channels = (
        await db.execute(select(func.count(UpstreamChannel.id)).where(UpstreamChannel.status == ChannelStatus.active))
    ).scalar() or 0
    return DashboardStats(
        total_users=users,
        total_balance=round(balance, 2),
        today_requests=today_req,
        today_revenue=round(today_rev, 4),
        active_channels=channels,
    )


@router.get("/users", response_model=list[UserOut])
async def list_users(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.id.desc()))
    return result.scalars().all()


@router.post("/users/{user_id}/toggle")
async def toggle_user(user_id: int, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能禁用管理员账号")
    user.is_active = not user.is_active
    await db.commit()
    return {"ok": True, "is_active": user.is_active}


@router.post("/recharge")
async def recharge(data: RechargeRequest, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == data.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user = await recharge_balance(db, user, data.amount, data.remark)
    return {"ok": True, "balance": user.balance}


@router.get("/channels", response_model=list[ChannelOut])
async def list_channels(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UpstreamChannel).order_by(UpstreamChannel.priority.desc()))
    channels = result.scalars().all()
    out = []
    for c in channels:
        item = ChannelOut.model_validate(c)
        item.api_key = _mask_key(c.api_key)
        out.append(item)
    return out


@router.post("/channels", response_model=ChannelOut)
async def create_channel(data: ChannelCreate, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    channel = UpstreamChannel(**data.model_dump())
    db.add(channel)
    await db.flush()
    # 自动为渠道声明的模型创建默认定价（在 commit 之前完成）
    created = await ensure_pricing_for_models(db, data.models)
    if created:
        channel.remark = (channel.remark or "") + f" | 自动创建定价: {','.join(created)}"
    await db.commit()
    await db.refresh(channel)
    return channel


@router.put("/channels/{channel_id}")
async def update_channel(
    channel_id: int,
    data: ChannelUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UpstreamChannel).where(UpstreamChannel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    old_models = channel.models
    updates = data.model_dump(exclude_unset=True)
    for k, v in updates.items():
        if k == "status" and v:
            setattr(channel, k, ChannelStatus(v))
        elif v is not None:
            setattr(channel, k, v)
    await db.flush()
    # 如果 models 字段有变化，自动为新模型创建定价
    new_models = updates.get("models")
    if new_models is not None and new_models != old_models:
        await ensure_pricing_for_models(db, new_models)
    await db.commit()
    return {"ok": True}


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UpstreamChannel).where(UpstreamChannel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    await db.delete(channel)
    await db.commit()
    return {"ok": True}


@router.get("/pricing", response_model=list[ModelPricingOut])
async def list_pricing(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelPricing).order_by(ModelPricing.id.desc()))
    return result.scalars().all()


@router.post("/pricing", response_model=ModelPricingOut)
async def create_pricing(data: ModelPricingCreate, admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(ModelPricing).where(ModelPricing.model == data.model))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="模型定价已存在")
    pricing = ModelPricing(**data.model_dump())
    db.add(pricing)
    await db.commit()
    await db.refresh(pricing)
    return pricing


@router.put("/pricing/{pricing_id}")
async def update_pricing(
    pricing_id: int,
    data: ModelPricingUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ModelPricing).where(ModelPricing.id == pricing_id))
    pricing = result.scalar_one_or_none()
    if not pricing:
        raise HTTPException(status_code=404, detail="定价不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(pricing, k, v)
    await db.commit()
    return {"ok": True}


@router.delete("/pricing/{pricing_id}")
async def delete_pricing(
    pricing_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ModelPricing).where(ModelPricing.id == pricing_id))
    pricing = result.scalar_one_or_none()
    if not pricing:
        raise HTTPException(status_code=404, detail="定价不存在")
    await db.delete(pricing)
    await db.commit()
    return {"ok": True}


@router.get("/usage")
async def admin_usage(admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UsageLog).order_by(UsageLog.id.desc()).limit(100))
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "model": l.model,
            "total_tokens": l.total_tokens,
            "cost": l.cost,
            "status": l.status,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.post("/redeem-codes", response_model=list[RedeemCodeOut])
async def create_redeem_codes(
    data: RedeemCodeCreate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """批量生成兑换码"""
    codes = []
    for _ in range(data.count):
        code = RedeemCode(
            code=secrets.token_urlsafe(16),
            amount=data.amount,
            remark=data.remark,
        )
        db.add(code)
        codes.append(code)
    await db.commit()
    for c in codes:
        await db.refresh(c)
    return codes


@router.get("/redeem-codes", response_model=list[RedeemCodeOut])
async def list_redeem_codes(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看所有兑换码"""
    result = await db.execute(select(RedeemCode).order_by(RedeemCode.id.desc()).limit(200))
    return result.scalars().all()


@router.get("/recharge-orders")
async def list_recharge_orders(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看所有充值订单"""
    result = await db.execute(
        select(RechargeOrder).order_by(RechargeOrder.id.desc()).limit(200)
    )
    orders = result.scalars().all()
    return [
        {
            "id": o.id,
            "order_no": o.order_no,
            "user_id": o.user_id,
            "amount": o.amount,
            "pay_method": o.pay_method,
            "status": o.status.value,
            "created_at": o.created_at.isoformat(),
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        }
        for o in orders
    ]
