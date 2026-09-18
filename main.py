from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager 
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

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

    # Silence unused-variable warnings while keeping settings loaded/validated at startup.
    _ = settings

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
