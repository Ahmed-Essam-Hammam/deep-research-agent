import os

os.environ.setdefault("POSTGRES_URL", "postgresql+asyncpg://postgres:postgres@localhost:5400/postgres")
os.environ.setdefault("SECRET_KEY_SIGN_TOKENS", "test-secret-key-do-not-use-in-production")
os.environ.setdefault("ENCRYPTION_ALGORITHM", "HS256")
os.environ.setdefault("TAVILY_API_KEY", "test-tavily-key")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGSMITH_API_KEY", "test-langsmith-key")

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


from src.models.db.entities.base import Base
from src.models.db.entities import conversations  
from src.models.db.entities import messages 
from src.models.db.entities import tokens   
from src.models.db.entities import users  
from src.dependencies.database import engine


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires a live Postgres+pgvector database (see docker-compose.yml)",
    )


async def database_reachable() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="session")
async def db_available() -> bool:
    return await database_reachable()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_schema(db_available):
    if not db_available:
        return
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture
async def db_session(db_available):
    if not db_available:
        pytest.skip("No reachable Postgres database - set POSTGRES_URL / run `docker-compose up`")

    async with engine.connect() as conn:
        outer_txn = await conn.begin()
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await outer_txn.rollback()


# ===== Small, reusable test data helpers =====

def unique_username(prefix: str = "user") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def future_expiry(minutes: int = 60) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)




