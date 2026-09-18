"""Router: groups the health controller under `/health`."""

from fastapi import APIRouter
from src.models.routes_schemes.http import HealthResponse



async def get_health() -> HealthResponse:
    """Handle `GET /api/health` - basic liveness check."""
    return HealthResponse(status="ok")

router = APIRouter(tags=["health"])

router.add_api_route("/health", get_health, methods=["GET"], response_model=HealthResponse)






