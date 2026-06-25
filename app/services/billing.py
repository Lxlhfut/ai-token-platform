from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, AgentCommission, AgentStatus, ModelPricing, Transaction, TransactionType, User
from app.routers.notifications import create_notification


async def get_model_pricing(db: AsyncSession, model: str) -> Optional[ModelPricing]:
    """查询模型定价，只做精确匹配，不再回退到 '*' 通配。每个模型必须显式定价。"""
    result = await db.execute(
        select(ModelPricing).where(ModelPricing.model == model, ModelPricing.is_active.is_(True))
    )
    return result.scalar_one_or_none()


def calculate_cost(pricing: Optional[ModelPricing], prompt_tokens: int, completion_tokens: int) -> float:
    """按模型定价计算费用。pricing 为 None 时直接 raise，禁止无定价调用。"""
    if not pricing:
        raise ValueError("模型无定价配置，拒绝计费")
    input_cost = (prompt_tokens / 1000) * pricing.input_price
    output_cost = (completion_tokens / 1000) * pricing.output_price
    return round(input_cost + output_cost, 6)


async def deduct_balance(
    db: AsyncSession,
    user: User,
    amount: float,
    remark: str,
) -> bool:
    if user.balance < amount:
        return False
    user.balance = round(user.balance - amount, 6)
    tx = Transaction(
        user_id=user.id,
        type=TransactionType.consume,
        amount=-amount,
        balance_after=user.balance,
        remark=remark,
    )
    db.add(tx)
    return True


async def ensure_pricing_for_models(
    db: AsyncSession,
    models_str: str,
    default_input: float = 0.002,
    default_output: float = 0.006,
) -> list[str]:
    """扫描渠道的 models 字段，对缺少定价的模型自动创建默认定价。
    返回本次新建了定价的模型名列表。跳过 '*' 通配符。"""
    if not models_str or models_str.strip() == "*":
        return []

    created = []
    for raw in models_str.split(","):
        model = raw.strip()
        if not model or model == "*":
            continue
        result = await db.execute(select(ModelPricing).where(ModelPricing.model == model))
        if result.scalar_one_or_none():
            continue  # 已有定价，跳过
        pricing = ModelPricing(
            model=model,
            input_price=default_input,
            output_price=default_output,
            description=f"自动创建（从渠道同步）",
        )
        db.add(pricing)
        created.append(model)

    if created:
        await db.flush()
    return created


async def recharge_balance(
    db: AsyncSession,
    user: User,
    amount: float,
    remark: Optional[str] = None,
    trigger_commission: bool = True,
) -> User:
    """给用户充值。若用户绑定了代理，自动给代理分配佣金（默认80%）。"""
    user.balance = round(user.balance + amount, 6)
    tx = Transaction(
        user_id=user.id,
        type=TransactionType.recharge,
        amount=amount,
        balance_after=user.balance,
        remark=remark or "管理员充值",
    )
    db.add(tx)

    # ===== 代理佣金分成 =====
    if trigger_commission and user.referrer_agent_id:
        agent_res = await db.execute(
            select(Agent).where(
                Agent.id == user.referrer_agent_id,
                Agent.status == AgentStatus.approved,
            )
        )
        agent = agent_res.scalar_one_or_none()
        if agent:
            commission_amount = round(amount * agent.commission_rate, 6)
            platform_amount = round(amount - commission_amount, 6)
            agent.available_commission = round(agent.available_commission + commission_amount, 6)
            agent.total_commission = round(agent.total_commission + commission_amount, 6)
            comm_record = AgentCommission(
                agent_id=agent.id,
                user_id=user.id,
                recharge_amount=amount,
                commission_amount=commission_amount,
                platform_amount=platform_amount,
                source="recharge",
                remark=remark or f"用户 #{user.id} 充值分成",
            )
            db.add(comm_record)

            # 通知代理：佣金到账
            await create_notification(
                db, agent.user_id, "commission_earned",
                f"您获得佣金 ¥{commission_amount:.4f}",
            )

    await db.commit()
    await db.refresh(user)
    return user

