from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from src.dependencies import database


@pytest.fixture
def client():
    # No `with` block: the lifespan (init_db) is deliberately not run.
    return TestClient(app)


def _fake_engine(connect_side_effect=None):
    conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn, side_effect=connect_side_effect)
    cm.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock()
    engine.connect.return_value = cm
    return engine


def test_liveness_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}



def test_metrics_endpoint_serves_prometheus_text(client):
    client.get("/api/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_request" in response.text


def test_metrics_not_routed_under_api_prefix(client):
    assert client.get("/api/metrics").status_code == 404


@pytest.mark.asyncio
async def test_init_db_is_non_destructive_and_takes_advisory_lock():
    conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)

    fake_engine = MagicMock()
    fake_engine.begin.return_value = cm
    with patch.object(database, "engine", fake_engine):
        await database.init_db()

    first_sql = str(conn.execute.await_args_list[0].args[0])
    assert "pg_advisory_xact_lock" in first_sql
    run_sync_targets = [call.args[0] for call in conn.run_sync.await_args_list]
    assert database.Base.metadata.create_all in run_sync_targets
    assert database.Base.metadata.drop_all not in run_sync_targets
