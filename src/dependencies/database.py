from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from src.models.db.entities.base import Base
from src.dependencies.injection import get_app_settings

settings = get_app_settings()

database_url = settings.postgres_url

engine = create_async_engine(database_url, echo=True)

# Arbitrary constant used as a Postgres advisory-lock key so that replicas
# starting at the same time initialise the schema one at a time.
_INIT_DB_LOCK_KEY = 7_240_001

async def init_db() -> None:
    async with engine.begin() as conn:

        await conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _INIT_DB_LOCK_KEY})
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)



async_session = async_sessionmaker(
    bind=engine, class_=AsyncSession, autoflush=False, expire_on_commit=False
)


async def get_db_session():
    try:
        async with async_session() as session:
            yield session

    except:
        await session.rollback()
        raise
    finally:
        await session.close()



DBsessionDep = Annotated[AsyncSession, Depends(get_db_session)]