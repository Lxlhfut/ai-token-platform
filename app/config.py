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

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()