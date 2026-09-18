from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from src.models.db.entities.base import Base
from src.dependencies.injection import get_app_settings

settings = get_app_settings()

database_url = settings.postgres_url

engine = create_async_engine(database_url, echo=True)

async def init_db() -> None:
    async with engine.begin() as conn:

        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
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