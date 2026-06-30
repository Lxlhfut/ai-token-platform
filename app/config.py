from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "dev-secret-key-change-in-production"
    database_url: str = "sqlite+aiosqlite:///./data/platform.db"
    admin_username: str = "admin"
    admin_password: str = "Admin123456!"
    platform_name: str = "AI Token 中转站"
    currency: str = "CNY"
    upstream_timeout: int = 120
    allow_registration: bool = True
    recharge_notice: str = "使用兑换码（卡密）即可自助充值，在下方「充值余额」框中输入兑换码，充值后余额立即到账，即可按量调用 AI 模型。"

    # 支付宝支付配置
    alipay_app_id: str = ""
    alipay_app_private_key: str = ""
    alipay_public_key: str = ""
    alipay_notify_url: str = ""
    alipay_return_url: str = ""

    # 微信支付 V3 Native 支付配置
    wechat_mch_id: str = ""
    wechat_app_id: str = ""
    wechat_api_v3_key: str = ""
    wechat_serial_no: str = ""
    wechat_private_key: str = ""
    wechat_notify_url: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def wechat_private_key_pem(self) -> str:
        """将 .env 中以 \n 分隔的私钥还原为真正的 PEM 格式（含真实换行）"""
        key = self.wechat_private_key.strip()
        if not key:
            return ""
        # 如果已经是多行（含真实换行），直接返回
        if "\r\n" in key or ("\n" in key and "-----BEGIN" in key and "KEY-----" in key):
            return key.replace("\\n", "\n")
        # .env 中 pydantic-settings 可能保留 literal \n 字符串
        if "\\n" in key:
            return key.replace("\\n", "\n")
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()