"""消息通知 API — 用户端和管理端共用"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Notification, User, UserRole

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


async def _ensure_user(user: User = Depends(get_current_user)):
    return user


async def _ensure_admin(user: User = Depends(get_current_user)):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@router.get("/unread-count")
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户未读消息数"""
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.is_read == False,
        )
    )
    count = result.scalar() or 0
    return {"count": count}


@router.get("/list")
async def list_notifications(
    limit: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的消息列表"""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.id.desc())
        .limit(limit)
    )
    records = result.scalars().all()

    type_label = {
        "commission_earned": "💰 佣金到账",
        "withdrawal_completed": "✅ 提现到账",
        "withdrawal_rejected": "❌ 提现拒绝",
        "agent_approved": "✅ 代理通过",
        "agent_rejected": "❌ 代理拒绝",
        "new_withdrawal": "📤 新提现申请",
        "new_agent_apply": "👤 新代理申请",
        "new_recharge_order": "💳 新充值待审核",
    }

    # 导航映射：消息类型 → 目标标签页 + 滚动区域 ID
    nav_map = {
        "new_agent_apply":   {"tab": "agents", "section": "agents-body"},
        "new_withdrawal":    {"tab": "agents", "section": "withdrawals-body"},
        "new_recharge_order": {"tab": "orders", "section": "orders-body"},
        "agent_approved":    {"tab": "agent",  "section": None},
        "agent_rejected":    {"tab": "agent",  "section": None},
        "withdrawal_completed": {"tab": "agent", "section": "withdrawal-history-body"},
        "withdrawal_rejected":  {"tab": "agent", "section": "withdrawal-history-body"},
        "commission_earned":    {"tab": "agent", "section": "agent-commissions-body"},
    }

    return [
        {
            "id": r.id,
            "type": r.type.value,
            "type_label": type_label.get(r.type.value, r.type.value),
            "title": r.title,
            "message": r.message,
            "is_read": r.is_read,
            "related_id": r.related_id,
            "nav_tab": (nav_map.get(r.type.value) or {}).get("tab"),
            "nav_section": (nav_map.get(r.type.value) or {}).get("section"),
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记单条消息为已读"""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    n = result.scalar_one_or_none()
    if not n:
        raise HTTPException(status_code=404, detail="消息不存在")
    n.is_read = True
    await db.commit()
    return {"ok": True}


@router.post("/read-all")
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记当前用户所有消息为已读"""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.is_read == False,
        )
    )
    unread = result.scalars().all()
    for n in unread:
        n.is_read = True
    await db.commit()
    return {"ok": True, "count": len(unread)}


# ======= 工具函数：在业务代码中调用，创建通知 =======

NOTIFY_TITLES = {
    "commission_earned": "佣金到账",
    "withdrawal_completed": "提现申请已打款",
    "withdrawal_rejected": "提现申请被拒绝",
    "agent_approved": "代理申请已通过",
    "agent_rejected": "代理申请被拒绝",
    "new_withdrawal": "新的提现申请",
    "new_agent_apply": "新的代理申请",
}


async def create_notification(
    db: AsyncSession,
    user_id: int,
    ntype: str,
    message: str,
    related_id: int = None,
):
    """创建一条通知"""
    from app.models import Notification, NotificationType
    n = Notification(
        user_id=user_id,
        type=NotificationType(ntype),
        title=NOTIFY_TITLES.get(ntype, ntype),
        message=message,
        related_id=related_id,
    )
    db.add(n)
    # 不在这里 commit，由调用方统一 commit
