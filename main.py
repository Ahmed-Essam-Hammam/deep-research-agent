from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager 
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.api_router import api_router
from src.config.settings import get_settings
from src.dependencies.database import init_db
from src.middleware.http_logging_middleware import add_request_logging_middleware
from src.middleware.rate_limiter import limiter, rate_limit_exceeded_handler

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

def create_app() -> FastAPI:
    """Application factory - builds a fully wired FastAPI instance."""
    settings = get_settings()

    app = FastAPI(
        title="Deep Research API",
        description="Multi-agent deep research system exposed over HTTP.",
        version="1.0.0",
        lifespan=lifespan
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)


    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    add_request_logging_middleware(app)

    app.include_router(api_router, prefix="/api")

    # Prometheus metrics. Served at /metrics (outside /api) so the Ingress, which only
    # routes /api, never exposes it publicly; Prometheus scrapes it in-cluster.
    # Its job is to automatically monitor your FastAPI endpoints and collect metrics.

    # For example, it can track:
    # - Number of HTTP requests.
    # - HTTP response status codes (200, 400, 500, etc.).
    # - Request processing duration (latency).
    # - Number of requests currently being processed.
    # What does instrument(app) do?

    # It attaches monitoring middleware to your FastAPI application.
    # Whenever a request comes in, the middleware collects relevant metrics about that request.
    Instrumentator(excluded_handlers=["/metrics"]).instrument(app)

    @app.get("/metrics", include_in_schema=False)
    # This decorator excludes /metrics from rate limiting.
    @limiter.exempt
    async def metrics() -> Response:
        # It collects the latest metric values from the Prometheus registry and converts them into Prometheus' text-based exposition format.
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


    # Silence unused-variable warnings while keeping settings loaded/validated at startup.
    _ = settings

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
