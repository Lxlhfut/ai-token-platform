from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, generate_api_key, get_current_user, hash_password, verify_password
from app.config import get_settings
from app.database import get_db
from app.models import (
    ApiKey,
    RedeemCode,
    RechargeOrder,
    RechargeOrderStatus,
    Transaction,
    TransactionType,
    User,
    UserRole,
)
from app.schemas import (
    ApiKeyCreate,
    ApiKeyOut,
    ModelPricingOut,
    RechargeOrderCreate,
    RechargeOrderOut,
    RedeemRequest,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRegister,
)

router = APIRouter(prefix="/api/user", tags=["user"])
settings = get_settings()


@router.post("/register", response_model=UserOut)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="当前不允许注册")

    if not data.agreed_terms:
        raise HTTPException(status_code=400, detail="请先阅读并同意用户注册协议和隐私政策")

    # 检查用户名是否已存在
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        role=UserRole.user,
        agreed_terms=True,
    )
    db.add(user)
    await db.flush()
    db.add(ApiKey(user_id=user.id, key=generate_api_key(), name="default"))
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已禁用")
    return TokenResponse(access_token=create_access_token(user.id, user.role.value))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.id.desc()))
    return result.scalars().all()


@router.post("/api-keys", response_model=ApiKeyOut)
async def create_api_key(data: ApiKeyCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApiKey).where(ApiKey.user_id == user.id))
    if len(result.scalars().all()) >= 5:
        raise HTTPException(status_code=400, detail="最多创建 5 个 API Key")
    key = ApiKey(user_id=user.id, key=generate_api_key(), name=data.name)
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key


@router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    await db.delete(key)
    await db.commit()
    return {"ok": True}


@router.get("/transactions")
async def list_transactions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.id.desc()).limit(50)
    )
    txs = result.scalars().all()
    return [
        {
            "id": t.id,
            "type": t.type.value,
            "amount": t.amount,
            "balance_after": t.balance_after,
            "remark": t.remark,
            "created_at": t.created_at.isoformat(),
        }
        for t in txs
    ]


@router.get("/usage")
async def list_usage(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import UsageLog

    result = await db.execute(
        select(UsageLog).where(UsageLog.user_id == user.id).order_by(UsageLog.id.desc()).limit(50)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "model": l.model,
            "prompt_tokens": l.prompt_tokens,
            "completion_tokens": l.completion_tokens,
            "total_tokens": l.total_tokens,
            "cost": l.cost,
            "status": l.status,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.get("/pricing", response_model=list[ModelPricingOut])
async def public_pricing(db: AsyncSession = Depends(get_db)):
    """公开模型定价，只展示有活跃上游渠道支撑的模型"""
    from app.models import ModelPricing, UpstreamChannel, ChannelStatus
    from app.schemas import ModelPricingOut
    from app.services.channel import channel_supports_model

    # 取活跃定价（排除 * 通配）
    p_result = await db.execute(
        select(ModelPricing)
        .where(ModelPricing.is_active.is_(True), ModelPricing.model != "*")
        .order_by(ModelPricing.id.asc())
    )
    pricings = p_result.scalars().all()

    # 取活跃渠道
    c_result = await db.execute(select(UpstreamChannel).where(UpstreamChannel.status == ChannelStatus.active))
    channels = c_result.scalars().all()

    # 只返回有渠道支撑的定价
    supported = []
    for p in pricings:
        for ch in channels:
            if channel_supports_model(ch, p.model):
                supported.append(p)
                break

    return supported


@router.post("/redeem")
async def redeem_code(data: RedeemRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """用户自助兑换码充值"""
    from app.services.billing import recharge_balance

    result = await db.execute(select(RedeemCode).where(RedeemCode.code == data.code.strip()))
    code_obj = result.scalar_one_or_none()

    if not code_obj:
        raise HTTPException(status_code=404, detail="兑换码不存在")
    if code_obj.is_used:
        raise HTTPException(status_code=400, detail="该兑换码已被使用")

    # 标记为已使用
    code_obj.is_used = True
    code_obj.used_by = user.id
    code_obj.used_at = datetime.now(timezone.utc)
    await db.flush()

    # 给用户充值
    user = await recharge_balance(db, user, code_obj.amount, f"兑换码充值 [{code_obj.code[:8]}...]")
    return {"ok": True, "amount": code_obj.amount, "balance": user.balance}


@router.post("/recharge-order", response_model=RechargeOrderOut)
async def create_recharge_order(
    data: RechargeOrderCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建扫码充值订单"""
    if data.pay_method not in ("wechat", "alipay"):
        raise HTTPException(status_code=400, detail="支付方式仅支持 wechat / alipay")
    if data.amount < 0.01:
        raise HTTPException(status_code=400, detail="充值金额不能低于 0.01 元")

    # 生成唯一订单号
    order_no = "R" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + secrets.token_hex(4).upper()

    order = RechargeOrder(
        order_no=order_no,
        user_id=user.id,
        amount=data.amount,
        pay_method=data.pay_method,
        status=RechargeOrderStatus.pending,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.post("/recharge-order/{order_no}/confirm")
async def confirm_recharge_order(
    order_no: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """模拟支付成功回调 — 用户扫码后点击「我已支付」确认"""
    from app.services.billing import recharge_balance

    result = await db.execute(
        select(RechargeOrder).where(
            RechargeOrder.order_no == order_no,
            RechargeOrder.user_id == user.id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != RechargeOrderStatus.pending:
        raise HTTPException(status_code=400, detail="订单状态异常（已支付或已取消）")

    # 标记已支付
    order.status = RechargeOrderStatus.paid
    order.paid_at = datetime.now(timezone.utc)
    await db.flush()

    # 给用户充值
    user = await recharge_balance(db, user, order.amount, f"扫码充值 [{order.pay_method}] #{order.order_no}")

    return {"ok": True, "amount": order.amount, "balance": user.balance}


@router.get("/recharge-orders")
async def list_recharge_orders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户查看自己的充值订单"""
    result = await db.execute(
        select(RechargeOrder)
        .where(RechargeOrder.user_id == user.id)
        .order_by(RechargeOrder.id.desc())
        .limit(20)
    )
    orders = result.scalars().all()
    return [
        {
            "id": o.id,
            "order_no": o.order_no,
            "amount": o.amount,
            "pay_method": o.pay_method,
            "status": o.status.value,
            "created_at": o.created_at.isoformat(),
            "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        }
        for o in orders
    ]
