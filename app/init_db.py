import os

from sqlalchemy import select, text

from app.auth import hash_password
from app.config import get_settings
from app.database import AsyncSessionLocal, Base, engine
from app.models import ModelPricing, User, UserRole

settings = get_settings()

DEFAULT_PRICING = [
    # 格式: (model, 本站输入价, 本站输出价, 官方输入价, 官方输出价, 描述)
    ("gpt-4o",         0.015, 0.06,  0.01875, 0.075,  "GPT-4o（官方价 $2.5/$10，本站 8 折）"),
    ("gpt-4o-mini",    0.001, 0.004, 0.00125, 0.005,  "GPT-4o Mini（官方价 $0.15/$0.6，本站 8 折）"),
    ("gpt-3.5-turbo",  0.0008, 0.0016, 0.00125, 0.0025, "GPT-3.5 Turbo"),
    ("claude-3-5-sonnet-20241022", 0.018, 0.09, 0.0225, 0.1125, "Claude 3.5 Sonnet（官方价 $3/$15，本站 8 折）"),
    ("deepseek-chat",  0.0005, 0.001, 0.0005, 0.001, "DeepSeek Chat（官方价同本站价）"),
]


async def _add_column_if_missing(conn, table: str, column: str, col_def: str):
    """通用迁移辅助：如果表中缺少某列则自动添加"""
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    columns = [row[1] for row in result.fetchall()]
    if column not in columns:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
        return True
    return False




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

    # ====== 补齐各表缺失的 created_at / cost_price / official_* 列（使用通用迁移辅助） ======
    # SQLite ALTER TABLE ADD COLUMN 不支持非恒定默认值（如 CURRENT_TIMESTAMP），统一用 NULL
    await _add_column_if_missing(conn, "model_pricing", "created_at", "TIMESTAMP DEFAULT NULL")
    await _add_column_if_missing(conn, "model_pricing", "cost_price", "FLOAT DEFAULT 0.0")
    await _add_column_if_missing(conn, "model_pricing", "official_input_price", "FLOAT DEFAULT 0.0")
    await _add_column_if_missing(conn, "model_pricing", "official_output_price", "FLOAT DEFAULT 0.0")
    await _add_column_if_missing(conn, "model_pricing", "tags", "VARCHAR(500) DEFAULT NULL")
    await _add_column_if_missing(conn, "api_keys", "allowed_models", "VARCHAR(2000) DEFAULT NULL")
    await _add_column_if_missing(conn, "upstream_channels", "created_at", "TIMESTAMP DEFAULT NULL")
    await _add_column_if_missing(conn, "model_fallbacks", "created_at", "TIMESTAMP DEFAULT NULL")



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
            for model, inp, out, off_in, off_out, desc in DEFAULT_PRICING:
                db.add(ModelPricing(
                    model=model, input_price=inp, output_price=out,
                    official_input_price=off_in, official_output_price=off_out,
                    description=desc,
                ))

        await db.commit()

