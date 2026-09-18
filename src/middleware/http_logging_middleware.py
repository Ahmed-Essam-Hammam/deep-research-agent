import time

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code, and duration for every request."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"[http] {request.method} {request.url.path} -> {response.status_code} ({elapsed_ms:.1f}ms)")
        return response


def add_request_logging_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestLoggingMiddleware)
