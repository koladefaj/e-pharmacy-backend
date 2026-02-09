import logging
import os
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.stripe
from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationFailed,
    NotAuthorized,
    PasswordVerificationError,
)
from app.core.limiter import limiter
from app.core.logging import request_id_var, setup_logging
from app.core.ssl import configure_ssl
from app.db.sessions import get_async_session

# LOGGING
setup_logging()
logger = logging.getLogger(__name__)

configure_ssl()

# APP INITIALIZATION
allowed_hosts = os.getenv("ALLOWED_HOSTS", "*").split(",")

app = FastAPI(
    title="E Pharmacy API",
    version="1.0.0",
)


@app.exception_handler(AuthenticationFailed)
@app.exception_handler(PasswordVerificationError)
async def auth_exception_handler(request: Request, exc: Exception):
    logger.warning(f"Auth failure: {str(exc)} | RequestID: {request.state.request_id}")
    return JSONResponse(
        status_code=401,
        content={"detail": str(exc)},
    )


@app.exception_handler(NotAuthorized)
async def not_authorized_handler(request: Request, exc: NotAuthorized):
    return JSONResponse(
        status_code=403,
        content={"detail": str(exc)},
    )


# ROUTERS
app.include_router(v1_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def universal_exception_handler(request: Request, exc: Exception):
    # Log the real error for the developer
    logger.error(f"Unhandled error: {str(exc)}", exc_info=True)

    # Send a polite message to the user
    return JSONResponse(
        status_code=500, content={"detail": "An unexpected error occurred."}
    )


# RATE LIMITING
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# SECURITY MIDDLEWARES
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


# REQUEST TRACING & SECURITY HEADERS
@app.middleware("http")
async def security_and_tracing_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    token = request_id_var.set(request_id)

    try:
        response = await call_next(request)

        response.headers["X-Request-Id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"

        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )

        return response

    except Exception as e:
        # Ensure we still reset the context var even if the app crashes
        logger.error(f"Middleware caught crash: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"detail": "Internal Server Error"}
        )

    finally:
        request_id_var.reset(token)


# HEALTH CHECKS
@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_async_session)):
    health_status = {"status": "healthy", "dependencies": {}}

    # 1. Check PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        health_status["dependencies"]["database"] = "ok"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["database"] = str(e)

    # 2. Check Redis
    try:
        redis_client = Redis.from_url(settings.redis_url)
        await redis_client.ping()
        health_status["dependencies"]["redis"] = "ok"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["dependencies"]["redis"] = str(e)

    return health_status
