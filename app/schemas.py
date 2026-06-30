from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=100)
    agreed_terms: bool = Field(default=False, description="必须勾选同意用户协议和隐私政策")
    invite_code: Optional[str] = Field(default=None, description="邀请码（可选）")


class UserLogin(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: Optional[str] = None
    username: str
    role: str
    balance: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreate(BaseModel):
    name: str = "default"
    allowed_models: Optional[list[str]] = []


class ApiKeyOut(BaseModel):
    id: int
    key: str
    name: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
    allowed_models: list[str] = []

    @field_validator('allowed_models', mode='before')
    @classmethod
    def _parse_allowed_models(cls, v):
        """将数据库中的 JSON 字符串解析为 list[str]"""
        if v is None or v == '':
            return []
        if isinstance(v, str):
            try:
                result = json.loads(v)
                return result if isinstance(result, list) else []
            except Exception:
                return []
        if isinstance(v, list):
            return v
        return []

    class Config:
        from_attributes = True


class ChannelCreate(BaseModel):
    name: str
    base_url: str
    api_key: str
    models: str = "*"
    weight: int = 100
    priority: int = 0
    remark: Optional[str] = None


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    models: Optional[str] = None
    weight: Optional[int] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class ChannelOut(BaseModel):
    id: int
    name: str
    base_url: str
    api_key: str
    models: str
    weight: int
    status: str
    priority: int
    remark: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ModelPricingCreate(BaseModel):
    model: str
    input_price: float
    output_price: float
    official_input_price: Optional[float] = 0.0
    official_output_price: Optional[float] = 0.0
    cost_price: Optional[float] = 0.0
    description: Optional[str] = None
    tags: Optional[list[str]] = []


class ModelPricingUpdate(BaseModel):
    model: Optional[str] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    official_input_price: Optional[float] = None
    official_output_price: Optional[float] = None
    cost_price: Optional[float] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    is_active: Optional[bool] = None


class ModelPricingOut(BaseModel):
    id: int
    model: str
    input_price: float
    output_price: float
    official_input_price: float = 0.0
    official_output_price: float = 0.0
    cost_price: float = 0.0
    description: Optional[str] = None
    tags: list[str] = []
    is_active: bool
    created_at: Optional[datetime] = None

    @field_validator('official_input_price', 'official_output_price', 'cost_price', mode='before')
    @classmethod
    def _none_to_zero(cls, v):
        """防御性转换：数据库迁移遗留的 NULL 值 → 0.0"""
        if v is None:
            return 0.0
        return v

    @field_validator('tags', mode='before')
    @classmethod
    def _parse_tags(cls, v):
        """将数据库中的 JSON 字符串解析为 list[str]"""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                result = json.loads(v)
                return result if isinstance(result, list) else []
            except Exception:
                return []
        if isinstance(v, list):
            return v
        return []

    class Config:
        from_attributes = True


# ======= 降级映射 =======

class FallbackCreate(BaseModel):
    source_model: str = Field(min_length=1, max_length=100)
    target_model: str = Field(min_length=1, max_length=100)
    priority: int = 0
    is_active: bool = True


class FallbackUpdate(BaseModel):
    source_model: Optional[str] = None
    target_model: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class FallbackOut(BaseModel):
    id: int
    source_model: str
    target_model: str
    priority: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ======= 毛利报告 =======

class MarginItem(BaseModel):
    """单个模型的毛利数据"""
    model: str
    cost_price: float = 0.0          # 上游成本
    selling_price: float = 0.0       # 售价（取 input_price 和 output_price 均值）
    input_price: float = 0.0
    output_price: float = 0.0
    profit: float = 0.0              # 利润
    margin_pct: float = 0.0          # 毛利率%
    usage_count: int = 0             # 近期调用次数
    revenue: float = 0.0             # 近期收入
    cost_total: float = 0.0          # 近期总成本
    profit_total: float = 0.0        # 近期总利润


class MarginReport(BaseModel):
    """毛利报告"""
    items: list[MarginItem]
    summary: dict      # {total_revenue, total_cost, total_profit, overall_margin_pct}


class RechargeRequest(BaseModel):
    user_id: int
    amount: float = Field(gt=0)
    remark: Optional[str] = None


class RedeemRequest(BaseModel):
    """用户兑换码充值请求"""
    code: str = Field(min_length=1, max_length=64)


class RedeemCodeCreate(BaseModel):
    """管理员创建兑换码请求"""
    amount: float = Field(gt=0, description="面值（元）")
    count: int = Field(default=1, ge=1, le=100, description="生成数量")
    remark: Optional[str] = None


class RedeemCodeOut(BaseModel):
    id: int
    code: str
    amount: float
    is_used: bool
    used_by: Optional[int] = None
    used_at: Optional[datetime] = None
    created_at: datetime
    remark: Optional[str] = None

    class Config:
        from_attributes = True


class UsageLogOut(BaseModel):
    id: int
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_users: int
    total_balance: float
    today_requests: int
    today_revenue: float
    active_channels: int


# ======= 扫码充值订单 =======
class RechargeOrderCreate(BaseModel):
    amount: float = Field(gt=0, description="充值金额（元）")
    pay_method: str = Field(pattern="^(wechat|alipay)$", description="支付方式")


class RechargeOrderOut(BaseModel):
    id: int
    order_no: str
    amount: float
    pay_method: str
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RechargeOrderVerify(BaseModel):
    """管理员审核订单"""
    action: str = Field(pattern="^(approve|reject)$")
    reason: Optional[str] = Field(default=None, max_length=255)


# ======= 平台收款码 =======
class PlatformQrcodeOut(BaseModel):
    pay_method: str
    amount: float
    qrcode_path: str


# ======= 代理系统 =======

class AgentApply(BaseModel):
    """申请成为代理"""
    remark: Optional[str] = Field(default=None, max_length=200, description="申请说明（可选）")


class AgentOut(BaseModel):
    """用户端代理信息"""
    id: int
    status: str
    invite_code: Optional[str] = None
    commission_rate: float
    total_commission: float
    available_commission: float
    default_qrcode_path: Optional[str] = None
    remark: Optional[str] = None
    applied_at: datetime
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentCommissionOut(BaseModel):
    """佣金明细"""
    id: int
    user_id: int
    recharge_amount: float
    commission_amount: float
    platform_amount: float
    source: str
    remark: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentWithdrawRequest(BaseModel):
    """代理提现申请（提现到微信/支付宝，管理员手动打款）"""
    amount: float = Field(gt=0, description="提现金额（元）")
    pay_method: str = Field(pattern="^(wechat|alipay)$", description="收款方式：wechat/alipay")
    pay_account: Optional[str] = Field(default=None, max_length=300, description="收款账号或备注（已弃用）")
    qrcode_path: Optional[str] = Field(default=None, max_length=500, description="收款码图片路径")


class WithdrawalOut(BaseModel):
    """用户端提现申请记录"""
    id: int
    amount: float
    pay_method: str
    pay_account: Optional[str] = None
    qrcode_path: Optional[str] = None
    status: str
    remark: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminWithdrawalOut(BaseModel):
    """管理端提现申请详情"""
    id: int
    agent_id: int
    user_id: int
    username: Optional[str] = None
    amount: float
    pay_method: str
    pay_account: Optional[str] = None
    qrcode_path: Optional[str] = None
    status: str
    remark: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminAgentOut(BaseModel):
    """管理端代理信息"""
    id: int
    user_id: int
    username: Optional[str] = None      # 通过联查填充
    invite_code: Optional[str] = None
    status: str
    commission_rate: float
    total_commission: float
    available_commission: float
    remark: Optional[str] = None
    applied_at: datetime
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True
