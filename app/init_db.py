import os

from sqlalchemy import select, text

from app.auth import hash_password
from app.config import get_settings
from app.database import AsyncSessionLocal, Base, engine
from app.models import ModelPricing, User, UserRole

settings = get_settings()

DEFAULT_PRICING = [
    ("gpt-4o", 0.015, 0.06, "GPT-4o"),
    ("gpt-4o-mini", 0.001, 0.004, "GPT-4o Mini"),
    ("gpt-3.5-turbo", 0.001, 0.002, "GPT-3.5 Turbo"),
    ("claude-3-5-sonnet-20241022", 0.018, 0.09, "Claude 3.5 Sonnet"),
    ("deepseek-chat", 0.0005, 0.001, "DeepSeek Chat"),
]


async def _run_migrations(conn):
    """对已存在的数据库进行增量迁移（添加新列/表等）"""
    # 检查 users 表是否有 referrer_agent_id 列
    result = await conn.execute(text("PRAGMA table_info(users)"))
    columns = [row[1] for row in result.fetchall()]
    if "referrer_agent_id" not in columns:
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN referrer_agent_id INTEGER")
        )

    # 检查 agent_withdrawals 表是否有 qrcode_path 列
    result = await conn.execute(text("PRAGMA table_info(agent_withdrawals)"))
    wd_columns = [row[1] for row in result.fetchall()]
    if "qrcode_path" not in wd_columns:
        await conn.execute(
            text("ALTER TABLE agent_withdrawals ADD COLUMN qrcode_path VARCHAR(500)")
        )

    # 检查 agents 表是否有 default_qrcode_path 列
    result = await conn.execute(text("PRAGMA table_info(agents)"))
    agent_columns = [row[1] for row in result.fetchall()]
    if "default_qrcode_path" not in agent_columns:
        await conn.execute(
            text("ALTER TABLE agents ADD COLUMN default_qrcode_path VARCHAR(500)")
        )

    # 检查 recharge_orders 表是否有 processor_id 列（审核系统）
    result = await conn.execute(text("PRAGMA table_info(recharge_orders)"))
    ro_columns = [row[1] for row in result.fetchall()]
    if "processor_id" not in ro_columns:
        await conn.execute(
            text("ALTER TABLE recharge_orders ADD COLUMN processor_id INTEGER")
        )
    if "processed_at" not in ro_columns:
        await conn.execute(
            text("ALTER TABLE recharge_orders ADD COLUMN processed_at TIMESTAMP")
        )
    # SQLite 的 Enum 字段通过 create_all 自动创建时已包含 submitted 状态
    # 存量数据库需手动确保 CHECK 约束包含 submitted


async def init_db():
    os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        # 先创建所有新表（agents, agent_commissions 等）
        await conn.run_sync(Base.metadata.create_all)
        # 再运行增量迁移（补充现有表的新列）
        await _run_migrations(conn)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == settings.admin_username))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                username=settings.admin_username,
                hashed_password=hash_password(settings.admin_password),
                role=UserRole.admin,
                balance=0,
            )
            db.add(admin)

        result = await db.execute(select(ModelPricing))
        if not result.scalars().first():
            for model, inp, out, desc in DEFAULT_PRICING:
                db.add(ModelPricing(model=model, input_price=inp, output_price=out, description=desc))

        await db.commit()

