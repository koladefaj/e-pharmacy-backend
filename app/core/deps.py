import logging
import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError
from sqlalchemy import select
from redis.asyncio import Redis
from app.core.config import settings

from app.core.roles import UserRole
from app.core.config import settings
from app.db.sessions import get_async_session
from app.models import User

# Initialize logger for security events
logger = logging.getLogger(__name__)

# HTTPBearer is used for "Authorization: Bearer <token>" headers
oauth2_scheme = HTTPBearer(auto_error=False)

redis_client: Redis | None = None

async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_async_session)
) -> User:
    """
    Dependency that authenticates requests using a JWT.
    
    Workflow:
    1. Extracts credentials from the Bearer token.
    2. Decodes and validates the JWT using the SECRET_KEY.
    3. Converts the string ID to a UUID object for SQLAlchemy compatibility.
    4. Lookups the user in the database to ensure they still exist and are active.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Decode the token
        payload = jwt.decode(
            token.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"leeway": 30}
        )
        
        user_id_str: str = payload.get("sub")

        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid authentication token"
            )
        if payload.get("type") == "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

    except JWTError:
        logger.warning(f"JWT Decode Failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token is invalid or has expired"
    )

    # --- DATABASE VERIFICATION ---
    
    # Convert the string user_id into a proper UUID object.
    # SQLAlchemy's Uui
    try:
        user_uuid = uuid.UUID(user_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier format"
        )

    # Query the database using the converted UUID object
    result = await session.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"Auth Failure: User {user_id_str} not found in database.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account disabled")


    return user


# --- ROLE BASED ACCESS CONTROL (SUB DEPENDENCIES OF GET CURRENT USER) ---

def get_current_customer(current_user: User = Depends(get_current_user)) -> User:
    """Require Customer role"""
    if current_user.role != UserRole.CUSTOMER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cant perform this action"
        )
    return current_user

def get_any_authenticated_user(current_user: User = Depends(get_current_user)) -> User:
    """Allows any logged-in user to see products"""
    return current_user

def get_current_pharmacist(current_user: User = Depends(get_current_user)) -> User:
    """Require Pharmacist Role"""
    if current_user.role != UserRole.PHARMACIST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pharmacist access required",
        )
    return current_user
    
def get_current_active_pharmacist(
    current_user: User = Depends(get_current_pharmacist)
) -> User:
    """Require verified pharmacist or admin"""
    if current_user.role == UserRole.PHARMACIST.value and not current_user.license_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending verification"
        )
    return current_user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

def get_allowed_password_changers(current_user: User = Depends(get_current_user)) -> User:
    """Require Customer or User role"""

    allowed_roles = [UserRole.CUSTOMER, UserRole.PHARMACIST]

    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to change password",
        )
    return current_user


# Depndecy Injection Services
async def get_redis() -> Redis:
    global redis_client

    if redis_client is None:
        redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    return redis_client


from redis.asyncio import Redis

# Create ONE Redis client (connection pool)
redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,  # important: returns str instead of bytes
)

async def get_redis() -> Redis:
    return redis_client

