"""Router: groups the health controller under `/health`."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from src.dependencies.database import engine
from src.models.routes_schemes.http import HealthResponse
from src.middleware.rate_limiter import limiter


async def get_health() -> HealthResponse:
    """Handle `GET /api/health` - basic liveness check."""
    return HealthResponse(status="ok")


async def get_ready() -> HealthResponse:
    """Handle `GET /api/health/ready` - readiness: can we reach the database?"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable") from exc
    return HealthResponse(status="ready")


# Probes (kubelet, ALB, Docker HEALTHCHECK) hit these constantly; they must never be rate limited.
limiter.exempt(get_health)
limiter.exempt(get_ready)

router = APIRouter(tags=["health"])

router.add_api_route("/health", get_health, methods=["GET"], response_model=HealthResponse)
router.add_api_route("/health/ready", get_ready, methods=["GET"], response_model=HealthResponse)