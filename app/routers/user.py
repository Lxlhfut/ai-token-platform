from datetime import datetime, timezone
import json
import secrets
import os
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, status, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, generate_api_key, get_current_user, hash_password, verify_password
from app.config import get_settings
from app.database import get_db
from app.models import (
    Agent,
    AgentCommission,
    AgentStatus,
    AgentWithdrawal,
    WithdrawalStatus,
    ApiKey,
    RedeemCode,
    RechargeOrder,
    RechargeOrderStatus,
    Transaction,
    TransactionType,
    User,
    UserRole,
)
from app.routers.notifications import create_notification
from app.schemas import (
    AgentApply,
    AgentCommissionOut,
    AgentOut,
    AgentWithdrawRequest,
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

    # 处理邀请码
    referrer_agent_id = None
    if data.invite_code:
        agent_res = await db.execute(
            select(Agent).where(
                Agent.invite_code == data.invite_code.strip(),
                Agent.status == AgentStatus.approved,
            )
        )
        agent = agent_res.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=400, detail="邀请码无效或已失效")
        referrer_agent_id = agent.id

    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        role=UserRole.user,
        agreed_terms=True,
        referrer_agent_id=referrer_agent_id,
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
    if data.allowed_models:
        key.allowed_models = json.dumps(data.allowed_models, ensure_ascii=False)
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key


@router.put("/api-keys/{key_id}", response_model=ApiKeyOut)
async def update_api_key(
    key_id: int,
    data: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """编辑 API Key 名称和允许的模型"""
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    if 'name' in data:
        key.name = data['name']
    if 'allowed_models' in data:
        key.allowed_models = json.dumps(data['allowed_models'] or [], ensure_ascii=False)
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

    p_result = await db.execute(
        select(ModelPricing)
        .where(ModelPricing.is_active.is_(True), ModelPricing.model != "*")
        .order_by(ModelPricing.id.asc())
    )
    pricings = p_result.scalars().all()

    c_result = await db.execute(select(UpstreamChannel).where(UpstreamChannel.status == ChannelStatus.active))
    channels = c_result.scalars().all()

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

    code_obj.is_used = True
    code_obj.used_by = user.id
    code_obj.used_at = datetime.now(timezone.utc)
    await db.flush()

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
    """用户扫码支付后点击「我已支付」— 需管理员审核后才到账"""
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
        raise HTTPException(status_code=400, detail="订单状态异常（已提交或已处理）")

    order.status = RechargeOrderStatus.submitted
    order.paid_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(order)

    from app.routers.notifications import create_notification
    admin_res = await db.execute(select(User).where(User.role == UserRole.admin))
    admins = admin_res.scalars().all()
    for admin in admins:
        await create_notification(
            db,
            admin.id,
            "new_recharge_order",
            f"用户 {user.username} 提交充值 ¥{order.amount}，待审核",
            related_id=order.id,
        )

    return {"ok": True, "message": "支付凭证已提交，等待管理员审核到账", "order_no": order_no, "status": "submitted"}


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


# ======= 代理中心 =======

@router.post("/agent/apply")
async def apply_agent(
    data: AgentApply,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """申请成为代理"""
    existing = await db.execute(select(Agent).where(Agent.user_id == user.id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您已提交过代理申请，请勿重复申请")

    agent = Agent(
        user_id=user.id,
        status=AgentStatus.pending,
        remark=data.remark,
    )
    db.add(agent)
    await db.flush()

    admins_res = await db.execute(select(User).where(User.role == UserRole.admin))
    for admin in admins_res.scalars().all():
        await create_notification(
            db, admin.id, "new_agent_apply",
            f"用户 {user.username} 申请成为代理", related_id=agent.id,
        )

    await db.commit()
    await db.refresh(agent)
    return {"ok": True, "message": "申请已提交，请等待管理员审批", "agent_id": agent.id}


@router.get("/agent/info", response_model=AgentOut)
async def get_agent_info(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取自己的代理信息"""
    result = await db.execute(select(Agent).where(Agent.user_id == user.id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="您尚未申请代理，或申请尚未生效")
    return agent


@router.get("/agent/commissions")
async def get_agent_commissions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取代理佣金明细"""
    agent_res = await db.execute(select(Agent).where(Agent.user_id == user.id))
    agent = agent_res.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="您尚未申请代理")

    result = await db.execute(
        select(AgentCommission)
        .where(AgentCommission.agent_id == agent.id)
        .order_by(AgentCommission.id.desc())
        .limit(100)
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


@router.post("/agent/withdraw")
async def agent_withdraw(
    data: AgentWithdrawRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """代理提现申请 — 提交到微信/支付宝，管理员手动核实后打款并标记完成"""
    agent_res = await db.execute(
        select(Agent).where(Agent.user_id == user.id, Agent.status == AgentStatus.approved)
    )
    agent = agent_res.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=403, detail="您不是活跃代理，无法提现")

    if data.amount > agent.available_commission:
        raise HTTPException(
            status_code=400,
            detail=f"提现金额超过可用佣金余额（当前可用：¥{agent.available_commission:.4f}）",
        )

    pending_res = await db.execute(
        select(AgentWithdrawal).where(
            AgentWithdrawal.agent_id == agent.id,
            AgentWithdrawal.status == WithdrawalStatus.pending,
        )
    )
    if pending_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您有待处理的提现申请，请等待管理员处理完成后再次提交")

    agent.available_commission = round(agent.available_commission - data.amount, 6)

    withdrawal = AgentWithdrawal(
        agent_id=agent.id,
        user_id=user.id,
        amount=data.amount,
        pay_method=data.pay_method,
        pay_account=data.pay_account,
        qrcode_path=data.qrcode_path,
        status=WithdrawalStatus.pending,
    )
    db.add(withdrawal)
    await db.flush()

    admins_res = await db.execute(select(User).where(User.role == UserRole.admin))
    for admin in admins_res.scalars().all():
        await create_notification(
            db, admin.id, "new_withdrawal",
            f"代理 {user.username} 提交提现申请 ¥{data.amount:.2f}", related_id=withdrawal.id,
        )

    await db.commit()
    await db.refresh(agent)
    return {
        "ok": True,
        "message": "提现申请已提交！将在约 1 小时内处理并打款至您的收款账户，请耐心等待。",
        "available_commission": agent.available_commission,
    }


@router.get("/agent/withdrawals")
async def get_agent_withdrawals(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查看提现申请历史"""
    agent_res = await db.execute(select(Agent).where(Agent.user_id == user.id))
    agent = agent_res.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="您尚未申请代理")

    result = await db.execute(
        select(AgentWithdrawal)
        .where(AgentWithdrawal.agent_id == agent.id)
        .order_by(AgentWithdrawal.id.desc())
        .limit(50)
    )
    records = result.scalars().all()
    pay_label = {"wechat": "微信", "alipay": "支付宝"}
    status_label = {"pending": "待处理", "completed": "已到账", "rejected": "已拒绝"}
    return [
        {
            "id": r.id,
            "amount": r.amount,
            "pay_method": pay_label.get(r.pay_method, r.pay_method),
            "pay_account": r.pay_account,
            "qrcode_path": r.qrcode_path,
            "status": status_label.get(r.status.value, r.status.value),
            "remark": r.remark,
            "created_at": r.created_at.isoformat(),
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
        }
        for r in records
    ]


# ======= 收款码上传 =======

@router.post("/agent/upload-qrcode")
async def upload_qrcode(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """上传收款码图片（微信/支付宝），返回存储路径"""
    allowed = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="仅支持 PNG / JPG / GIF / WebP 格式")
    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "gif", "webp"):
        raise HTTPException(status_code=400, detail="不支持的文件扩展名")

    upload_dir = os.path.join("app", "static", "uploads", "qrcodes")
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_dir, filename)

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片大小不能超过 2MB")

    with open(filepath, "wb") as f:
        f.write(content)

    url = f"/static/uploads/qrcodes/{filename}"
    return {"ok": True, "url": url}


@router.post("/agent/bind-qrcode")
async def bind_default_qrcode(
    qrcode_path: str = Body(..., embed=True),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """将收款码绑定为代理的默认收款码（一键绑定）
    
    请求体：{"qrcode_path": "/static/uploads/qrcodes/xxx.png"}
    绑定后，每次发起提现时默认使用该收款码，无需重复上传。
    """
    from fastapi import Body

    agent_res = await db.execute(
        select(Agent).where(Agent.user_id == user.id, Agent.status == AgentStatus.approved)
    )
    agent = agent_res.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=403, detail="您不是活跃代理，无法绑定收款码")

    if not qrcode_path.startswith("/static/uploads/qrcodes/"):
        raise HTTPException(status_code=400, detail="无效的收款码路径，请先上传收款码")

    agent.default_qrcode_path = qrcode_path
    await db.commit()
    await db.refresh(agent)
    return {"ok": True, "message": "收款码已绑定，后续提现将默认使用此收款码", "qrcode_path": qrcode_path}
