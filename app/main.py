import uuid
import os
import logging

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.logging import setup_logging, request_id_var
from app.core.limiter import limiter
from app.core.deps import get_redis
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import AuthenticationFailed, NotAuthorized, PasswordVerificationError



# --------------------------------------------------
# LOGGING
# --------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)

# --------------------------------------------------
# APP INITIALIZATION (ONLY ONCE ✅)
# --------------------------------------------------
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

# --------------------------------------------------
# ROUTERS
# --------------------------------------------------
app.include_router(v1_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def universal_exception_handler(request: Request, exc: Exception):
    # Log the real error for the developer
    logger.error(f"Unhandled error: {str(exc)}", exc_info=True)
    
    # Send a polite message to the user
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."}
    )

# --------------------------------------------------
# RATE LIMITING
# --------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --------------------------------------------------
# SECURITY MIDDLEWARES
# --------------------------------------------------
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:3000",
        "https://your-frontend.up.railway.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# REQUEST TRACING & SECURITY HEADERS
# --------------------------------------------------
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
    finally:
        request_id_var.reset(token)

# --------------------------------------------------
# HEALTH CHECKS
# --------------------------------------------------
@app.get("/health", status_code=200)
def health_check(request: Request):
    return {
        "status": "online",
        "request_id": request.state.request_id,
        "environment": settings.environment,
    }

@app.get("/redis-health")
async def redis_health(redis=Depends(get_redis)):
    await redis.set("health", "ok", ex=5)
    return {"redis": await redis.get("health")}
