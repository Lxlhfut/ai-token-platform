from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_admin_user
from app.database import get_db
from app.routers.notifications import create_notification
from app.models import (
    Agent,
    AgentCommission,
    AgentStatus,
    AgentWithdrawal,
    WithdrawalStatus,
    ChannelStatus,
    ModelPricing,
    PlatformQrcode,
    RechargeOrder,
    RechargeOrderStatus,
    RedeemCode,
    Transaction,
    UpstreamChannel,
    UsageLog,
    User,
    UserRole,
)
from app.schemas import (
    AdminAgentOut,
    ChannelCreate,
    ChannelOut,
    ChannelUpdate,
    DashboardStats,
    ModelPricingCreate,
    ModelPricingOut,
    ModelPricingUpdate,
    PlatformQrcodeOut,
    RechargeOrderOut,
    RechargeOrderVerify,
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


@router.post("/recharge-orders/{order_id}/verify")
async def verify_recharge_order(
    order_id: int,
    data: RechargeOrderVerify,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """审核充值订单 — approve 确认到账 / reject 拒绝"""
    result = await db.execute(
        select(RechargeOrder).where(RechargeOrder.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != RechargeOrderStatus.submitted:
        raise HTTPException(status_code=400, detail="订单状态不是「待审核」")

    if data.action == "approve":
        order.status = RechargeOrderStatus.paid
        order.processor_id = admin.id
        order.processed_at = datetime.now(timezone.utc)
        await db.flush()

        user_res = await db.execute(select(User).where(User.id == order.user_id))
        order_user = user_res.scalar_one_or_none()
        if order_user:
            await recharge_balance(db, order_user, order.amount,
                                   f"扫码充值 [{order.pay_method}] #{order.order_no}")

        # 通知用户充值到账
        await create_notification(
            db, order.user_id, "commission_earned",
            f"充值 ¥{order.amount} 已到账，当前余额 ¥{order_user.balance:.2f}"
            if order_user else f"充值 ¥{order.amount} 已到账",
        )
        return {"ok": True, "message": "已确认到账", "status": "paid"}

    else:  # reject
        order.status = RechargeOrderStatus.cancelled
        order.processor_id = admin.id
        order.processed_at = datetime.now(timezone.utc)
        await db.commit()
        return {"ok": True, "message": "已拒绝", "status": "cancelled"}


# ======= 平台收款码管理 =======

PLATFORM_AMOUNTS = [2, 5, 10, 20, 50, 100, 500]

@router.get("/platform-qrcodes", response_model=list[PlatformQrcodeOut])
async def list_platform_qrcodes(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看所有平台收款码"""
    result = await db.execute(
        select(PlatformQrcode).order_by(PlatformQrcode.pay_method, PlatformQrcode.amount)
    )
    records = result.scalars().all()
    return [
        PlatformQrcodeOut(pay_method=r.pay_method, amount=r.amount, qrcode_path=r.qrcode_path)
        for r in records
    ]


@router.post("/platform-qrcode")
async def upload_platform_qrcode(
    pay_method: str = Form(..., description="wechat 或 alipay"),
    amount: float = Form(..., description="固定金额"),
    file: UploadFile = File(...),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """上传/更新某个 (付款方式, 固定金额) 的收款码"""
    if pay_method not in ("wechat", "alipay"):
        raise HTTPException(status_code=400, detail="支付方式仅支持 wechat / alipay")
    if amount not in PLATFORM_AMOUNTS:
        raise HTTPException(status_code=400, detail=f"金额仅支持: {', '.join(str(a) for a in PLATFORM_AMOUNTS)}")

    allowed = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="仅支持 PNG / JPG / GIF / WebP 格式")
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "gif", "webp"):
        raise HTTPException(status_code=400, detail="不支持的文件扩展名")

    upload_dir = os.path.join("app", "static", "uploads", "platform")
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{pay_method}_{int(amount)}.{ext}"
    filepath = os.path.join(upload_dir, filename)

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 2MB")

    with open(filepath, "wb") as f:
        f.write(content)

    url = f"/static/uploads/platform/{filename}"

    # 更新或创建数据库记录
    existing = await db.execute(
        select(PlatformQrcode).where(
            PlatformQrcode.pay_method == pay_method,
            PlatformQrcode.amount == amount,
        )
    )
    record = existing.scalar_one_or_none()
    if record:
        record.qrcode_path = url
    else:
        record = PlatformQrcode(pay_method=pay_method, amount=amount, qrcode_path=url)
        db.add(record)
    await db.commit()

    return {"ok": True, "url": url, "pay_method": pay_method, "amount": amount}


# ======= 代理管理 =======

@router.get("/agents")
async def list_agents(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有代理申请列表"""
    result = await db.execute(select(Agent).order_by(Agent.id.desc()))
    agents = result.scalars().all()

    # 批量查用户名
    user_ids = [a.user_id for a in agents]
    users_res = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u.username for u in users_res.scalars().all()}

    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "username": users_map.get(a.user_id, ""),
            "invite_code": a.invite_code,
            "status": a.status.value,
            "commission_rate": a.commission_rate,
            "total_commission": a.total_commission,
            "available_commission": a.available_commission,
            "remark": a.remark,
            "applied_at": a.applied_at.isoformat(),
            "approved_at": a.approved_at.isoformat() if a.approved_at else None,
        }
        for a in agents
    ]


@router.post("/agents/{agent_id}/approve")
async def approve_agent(
    agent_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """审批通过代理申请，并生成唯一邀请码"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="代理记录不存在")
    if agent.status == AgentStatus.approved:
        raise HTTPException(status_code=400, detail="该代理已经通过审批")

    # 生成唯一邀请码
    while True:
        code = secrets.token_urlsafe(8).upper()[:10]
        existing = await db.execute(select(Agent).where(Agent.invite_code == code))
        if not existing.scalar_one_or_none():
            break

    agent.status = AgentStatus.approved
    agent.invite_code = code
    agent.approved_at = datetime.now(timezone.utc)

    # 通知代理用户
    await create_notification(
        db, agent.user_id, "agent_approved",
        f"您的代理申请已通过！邀请码：{code}", related_id=agent.id,
    )

    await db.commit()
    return {"ok": True, "invite_code": code, "message": "代理审批通过"}


@router.post("/agents/{agent_id}/reject")
async def reject_agent(
    agent_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """拒绝代理申请"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="代理记录不存在")
    if agent.status not in (AgentStatus.pending,):
        raise HTTPException(status_code=400, detail="只能拒绝待审批状态的申请")
    agent.status = AgentStatus.rejected

    # 通知代理用户
    await create_notification(
        db, agent.user_id, "agent_rejected",
        "您的代理申请被拒绝，如有疑问请联系管理员", related_id=agent.id,
    )

    await db.commit()
    return {"ok": True, "message": "代理申请已拒绝"}


@router.post("/agents/{agent_id}/disable")
async def disable_agent(
    agent_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """禁用/恢复代理（切换状态）"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="代理记录不存在")

    if agent.status == AgentStatus.approved:
        agent.status = AgentStatus.disabled
        msg = "代理已禁用"
    elif agent.status == AgentStatus.disabled:
        agent.status = AgentStatus.approved
        msg = "代理已恢复"
    else:
        raise HTTPException(status_code=400, detail="只能禁用/恢复已通过的代理")

    await db.commit()
    return {"ok": True, "status": agent.status.value, "message": msg}


@router.get("/agents/{agent_id}/commissions")
async def get_agent_commissions(
    agent_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """查看指定代理的佣金记录"""
    result = await db.execute(
        select(AgentCommission)
        .where(AgentCommission.agent_id == agent_id)
        .order_by(AgentCommission.id.desc())
        .limit(200)
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "recharge_amount": r.recharge_amount,
            "commission_amount": r.commission_amount,
            "platform_amount": r.platform_amount,
            "source": r.source,
            "remark": r.remark,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


# ======= 提现申请管理 =======

@router.get("/agent-withdrawals")
async def list_agent_withdrawals(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有提现申请列表（默认最新100条）"""
    result = await db.execute(
        select(AgentWithdrawal).order_by(AgentWithdrawal.id.desc()).limit(100)
    )
    withdrawals = result.scalars().all()

    # 批量查用户名
    user_ids = list({w.user_id for w in withdrawals})
    users_res = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u.username for u in users_res.scalars().all()}

    pay_label = {"wechat": "微信", "alipay": "支付宝"}
    status_label = {"pending": "待处理", "completed": "已到账", "rejected": "已拒绝"}
    status_color = {"pending": "var(--warning,#f59e0b)", "completed": "#22c55e", "rejected": "var(--danger)"}

    return [
        {
            "id": w.id,
            "agent_id": w.agent_id,
            "user_id": w.user_id,
            "username": users_map.get(w.user_id, ""),
            "amount": w.amount,
            "pay_method": pay_label.get(w.pay_method, w.pay_method),
            "pay_method_raw": w.pay_method,
            "pay_account": w.pay_account,
            "qrcode_path": w.qrcode_path,
            "status": status_label.get(w.status.value, w.status.value),
            "status_raw": w.status.value,
            "status_color": status_color.get(w.status.value, ""),
            "remark": w.remark,
            "created_at": w.created_at.isoformat(),
            "processed_at": w.processed_at.isoformat() if w.processed_at else None,
        }
        for w in withdrawals
    ]


@router.post("/agent-withdrawals/{withdrawal_id}/complete")
async def complete_agent_withdrawal(
    withdrawal_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """确认已打款 — 标记提现申请为已完成"""
    result = await db.execute(select(AgentWithdrawal).where(AgentWithdrawal.id == withdrawal_id))
    w = result.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="提现申请不存在")
    if w.status != WithdrawalStatus.pending:
        raise HTTPException(status_code=400, detail="该申请已处理，无需重复操作")

    w.status = WithdrawalStatus.completed
    w.processed_at = datetime.now(timezone.utc)
    w.processor_id = admin.id

    # 通知代理用户
    await create_notification(
        db, w.user_id, "withdrawal_completed",
        f"提现申请 ¥{w.amount:.2f} 已打款到您的收款账户", related_id=w.id,
    )

    await db.commit()
    return {"ok": True, "message": "已标记为打款完成"}


@router.post("/agent-withdrawals/{withdrawal_id}/reject")
async def reject_agent_withdrawal(
    withdrawal_id: int,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """拒绝提现申请并退回冻结佣金"""
    result = await db.execute(select(AgentWithdrawal).where(AgentWithdrawal.id == withdrawal_id))
    w = result.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="提现申请不存在")
    if w.status != WithdrawalStatus.pending:
        raise HTTPException(status_code=400, detail="该申请已处理，无法拒绝")

    # 退回冻结的佣金
    agent_res = await db.execute(select(Agent).where(Agent.id == w.agent_id))
    agent = agent_res.scalar_one_or_none()
    if agent:
        agent.available_commission = round(agent.available_commission + w.amount, 6)

    w.status = WithdrawalStatus.rejected
    w.processed_at = datetime.now(timezone.utc)
    w.processor_id = admin.id

    # 通知代理用户
    await create_notification(
        db, w.user_id, "withdrawal_rejected",
        f"提现申请 ¥{w.amount:.2f} 被拒绝，佣金已退回您的账户", related_id=w.id,
    )

    await db.commit()
    return {"ok": True, "message": "提现申请已拒绝，佣金已退回代理账户"}


