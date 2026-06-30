<<<<<<< HEAD
from pathlib import Path

=======
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

<<<<<<< HEAD
# 将相对 SQLite 路径解析为项目根目录绝对路径，避免 "unable to open database file"
_db_url = settings.database_url
if _db_url.startswith("sqlite"):
    import re
    m = re.search(r"sqlite(\+aiosqlite)?:///(.+)", _db_url)
    if m:
        rel_path = m.group(2)
        # 如果是相对路径，相对于项目根目录进行解析
        if not Path(rel_path).is_absolute():
            project_root = Path(__file__).resolve().parent.parent  # app/.. → 项目根目录
            abs_path = (project_root / rel_path).resolve()
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            _db_url = _db_url.replace(rel_path, str(abs_path).replace("\\", "/"))

engine = create_async_engine(_db_url, echo=False)
=======
engine = create_async_engine(settings.database_url, echo=False)
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
