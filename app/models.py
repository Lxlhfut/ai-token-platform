from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class ChannelStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class TransactionType(str, enum.Enum):
    recharge = "recharge"
    consume = "consume"
    refund = "refund"
    adjust = "adjust"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True, nullable=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    agreed_terms: Mapped[bool] = mapped_column(Boolean, default=False)
    referrer_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=None
    )  # 注册时填写邀请码后绑定的代理ID（逻辑外键）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    usage_logs: Mapped[list["UsageLog"]] = relationship(back_populates="user")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), default="default")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    allowed_models: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True, comment="允许调用的模型 JSON 数组，空表示全部")

    user: Mapped["User"] = relationship(back_populates="api_keys")


class UpstreamChannel(Base):
    __tablename__ = "upstream_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(500))
    api_key: Mapped[str] = mapped_column(String(500))
    models: Mapped[str] = mapped_column(Text, default="*")
    weight: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[ChannelStatus] = mapped_column(Enum(ChannelStatus), default=ChannelStatus.active)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    remark: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    usage_logs: Mapped[list["UsageLog"]] = relationship(back_populates="channel")


class ModelPricing(Base):
    __tablename__ = "model_pricing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    input_price: Mapped[float] = mapped_column(Float, default=0.0)
    output_price: Mapped[float] = mapped_column(Float, default=0.0)
    official_input_price: Mapped[float] = mapped_column(Float, default=0.0, comment="官方输入价格（元/1K tokens），用于展示折扣")
    official_output_price: Mapped[float] = mapped_column(Float, default=0.0, comment="官方输出价格（元/1K tokens），用于展示折扣")
    cost_price: Mapped[float] = mapped_column(Float, default=0.0, comment="上游成本价格（元/1K tokens），用于毛利计算")
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="模型标签 JSON 数组，如 [\"特价\",\"快速\"]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ModelFallback(Base):
    """降级映射 — 模型不可用时自动切换到备用模型"""
    __tablename__ = "model_fallbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_model: Mapped[str] = mapped_column(String(100), index=True)
    target_model: Mapped[str] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer, default=0)   # 降级优先级（数字越小越优先）
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    channel_id: Mapped[Optional[int]] = mapped_column(ForeignKey("upstream_channels.id"), nullable=True)
    api_key_id: Mapped[Optional[int]] = mapped_column(ForeignKey("api_keys.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="usage_logs")
    channel: Mapped[Optional["UpstreamChannel"]] = relationship(back_populates="usage_logs")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    amount: Mapped[float] = mapped_column(Float)
    balance_after: Mapped[float] = mapped_column(Float)
    remark: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="transactions")


class RedeemCode(Base):
    """兑换码（卡密）表 - 用户自助充值用"""
    __tablename__ = "redeem_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Float)          # 面值（元）
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    used_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class AgentStatus(str, enum.Enum):
    pending = "pending"      # 待审批
    approved = "approved"    # 已审批（激活）
    rejected = "rejected"    # 已拒绝
    disabled = "disabled"    # 已禁用


class Agent(Base):
    """代理表 — 一个用户最多只能有一条代理记录"""
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    invite_code: Mapped[Optional[str]] = mapped_column(String(32), unique=True, index=True, nullable=True)
    status: Mapped[AgentStatus] = mapped_column(Enum(AgentStatus), default=AgentStatus.pending)
    commission_rate: Mapped[float] = mapped_column(Float, default=0.80)   # 代理佣金比例（默认80%）
    total_commission: Mapped[float] = mapped_column(Float, default=0.0)   # 累计已产生的佣金
    available_commission: Mapped[float] = mapped_column(Float, default=0.0)  # 可提现佣金余额
    default_qrcode_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 绑定的默认收款码
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AgentCommission(Base):
    """代理佣金明细记录"""
    __tablename__ = "agent_commissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))   # 充值用户
    recharge_amount: Mapped[float] = mapped_column(Float)           # 充值金额
    commission_amount: Mapped[float] = mapped_column(Float)         # 代理获得佣金（80%）
    platform_amount: Mapped[float] = mapped_column(Float)           # 平台获得金额（20%）
    source: Mapped[str] = mapped_column(String(50), default="recharge")  # recharge
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WithdrawalStatus(str, enum.Enum):
    pending = "pending"        # 待处理（管理员待打款）
    completed = "completed"    # 已完成（管理员已打款）
    rejected = "rejected"      # 已拒绝


class AgentWithdrawal(Base):
    """代理提现申请 — 代理申请将佣金提现到微信/支付宝，管理员手动打款后标记完成"""
    __tablename__ = "agent_withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float)                    # 申请提现金额
    pay_method: Mapped[str] = mapped_column(String(20))             # wechat / alipay
    pay_account: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)  # 收款账号/备注（已弃用，改用 qrcode_path）
    qrcode_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # 收款码图片路径
    status: Mapped[WithdrawalStatus] = mapped_column(Enum(WithdrawalStatus), default=WithdrawalStatus.pending)
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)        # 管理员备注
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    processor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)      # 处理管理员ID


class NotificationType(str, enum.Enum):
    commission_earned = "commission_earned"           # 佣金到账（通知代理）
    withdrawal_completed = "withdrawal_completed"     # 提现已打款（通知代理）
    withdrawal_rejected = "withdrawal_rejected"       # 提现已拒绝（通知代理）
    agent_approved = "agent_approved"                 # 代理审批通过（通知用户）
    agent_rejected = "agent_rejected"                 # 代理审批拒绝（通知用户）
    new_withdrawal = "new_withdrawal"                 # 新提现申请（通知管理员）
    new_agent_apply = "new_agent_apply"               # 新代理申请（通知管理员）
    new_recharge_order = "new_recharge_order"         # 新充值订单待审核（通知管理员）


class Notification(Base):
    """消息通知表"""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # 接收者
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    title: Mapped[str] = mapped_column(String(100))
    message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    related_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 关联业务 ID
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class RechargeOrderStatus(str, enum.Enum):
    pending = "pending"          # 已创建，等待用户支付
    submitted = "submitted"      # 用户已提交支付凭证，等待管理员审核
    paid = "paid"                # 管理员已确认到账
    cancelled = "cancelled"      # 已取消/已拒绝


class RechargeOrder(Base):
    """充值订单表 - 用户扫码自助充值"""
    __tablename__ = "recharge_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[float] = mapped_column(Float)               # 充值金额（元）
    pay_method: Mapped[str] = mapped_column(String(20))        # wechat / alipay
    status: Mapped[RechargeOrderStatus] = mapped_column(
        Enum(RechargeOrderStatus), default=RechargeOrderStatus.pending
    )
    processor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 审核管理员ID
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PlatformQrcode(Base):
    """平台收款码表 — 每个 (pay_method, amount) 组合一张收款码"""
    __tablename__ = "platform_qrcodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pay_method: Mapped[str] = mapped_column(String(20))      # wechat / alipay
    amount: Mapped[float] = mapped_column(Float)             # 固定金额（元）
    qrcode_path: Mapped[str] = mapped_column(String(500))    # 图片路径
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
