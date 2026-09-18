import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies.database import async_session, engine, get_db_session, init_db


# ===== Engine / sessionmaker configuration (no DB connection needed) =====

def test_engine_url_matches_configured_postgres_url():
    configured = os.environ["POSTGRES_URL"]

    assert engine.url.drivername in configured
    assert engine.url.database in configured



# ===== get_db_session(): control-flow contract, mocked (no DB needed) =====

@pytest.mark.asyncio
async def test_get_db_session_yields_a_usable_session_object():
    fake_session = AsyncMock(spec=AsyncSession)
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("src.dependencies.database.async_session", return_value=fake_cm):
        gen = get_db_session()
        yielded = await gen.__anext__()
        assert yielded is fake_session

        # Drain the generator the way FastAPI does on a clean request.
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    fake_session.close.assert_awaited()


@pytest.mark.asyncio
async def test_get_db_session_propagates_exceptions_raised_by_the_caller():

    fake_session = AsyncMock(spec=AsyncSession)
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_session)
    fake_cm.__aexit__ = AsyncMock(return_value=False)

    class BoomError(Exception):
        pass

    with patch("src.dependencies.database.async_session", return_value=fake_cm):
        gen = get_db_session()
        await gen.__anext__()
        with pytest.raises(BoomError):
            await gen.athrow(BoomError("simulated handler failure"))

    fake_session.rollback.assert_awaited()


# ===== Integration: requires a real Postgres+pgvector instance =====

@pytest.mark.integration
@pytest.mark.asyncio
async def test_init_db_creates_the_pgvector_extension_and_all_tables(db_available):
    if not db_available:
        pytest.skip("No reachable Postgres database")

    await init_db()

    async with engine.connect() as conn:
        ext_installed = await conn.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        )
        assert ext_installed.first() is not None

        for table_name in ("users", "tokens", "conversations", "messages"):
            result = await conn.execute(
                text("SELECT to_regclass(:name)"), {"name": table_name}
            )
            assert result.scalar() is not None, f"expected table '{table_name}' to exist after init_db()"
