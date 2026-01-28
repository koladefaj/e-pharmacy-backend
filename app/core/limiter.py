import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

# Initialize logger
logger = logging.getLogger(__name__)

storage_uri = settings.redis_url if settings.environment != "testing" else "memory://"
IS_TESTING = settings.environment == "testing"

# RATE LIMITER CONFIGURATION 
# key_func=get_remote_address: Identifies users by their IP address.


limiter = Limiter(
    key_func=get_remote_address,
    # This points to Redis instance so limits are shared across all Docker containers
    storage_uri=f"{storage_uri}",
    strategy="fixed-window",
    enabled=not IS_TESTING
)

def init_limiter_error_handlers(app):
    """
    Registers a custom error handler to return 
    a clean JSON response when a user is rate-limited.
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from slowapi.errors import RateLimitExceeded

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        ip = request.client.host if request.client else "unknown"
        logger.warning(f"Rate limit exceeded by IP: {ip}")
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please slow down."},
        )