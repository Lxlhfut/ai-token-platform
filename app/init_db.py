import os

from sqlalchemy import select

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


async def init_db():
    os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
