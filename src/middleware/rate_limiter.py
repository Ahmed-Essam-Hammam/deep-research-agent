from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "60 per hour", "2/5seconds"],
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    retry_after = int(exc.description.split(" ")[-1])

    response_body = {
        "detail": "Rate limit exceeded. Please try again later.",
        "retry_after_seconds": retry_after,
    }

    return JSONResponse(
        status_code=429,
        content=response_body,
        headers={
            "Retry-After": str(retry_after),
        },
    )
