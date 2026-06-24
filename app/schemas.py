from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=100)
    agreed_terms: bool = Field(default=False, description="必须勾选同意用户协议和隐私政策")


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


class ApiKeyOut(BaseModel):
    id: int
    key: str
    name: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None

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
    description: Optional[str] = None


class ModelPricingUpdate(BaseModel):
    model: Optional[str] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ModelPricingOut(BaseModel):
    id: int
    model: str
    input_price: float
    output_price: float
    description: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True
