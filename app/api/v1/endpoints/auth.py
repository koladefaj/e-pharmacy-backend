import logging
from fastapi import Depends, APIRouter, Request, Body
from starlette import status
from app.schemas.user import RegisterCustomerRequest, LoginRequest
from app.services.auth_service import AuthService
from app.schemas.user import RefreshTokenRequest
from app.core.limiter import limiter

# Initialize logger for security and audit events
logger = logging.getLogger(__name__)

router = APIRouter( prefix="/auth", tags=["auth"],)

@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")  # Strict limit to prevent bot-spamming account creation
async def signup(
    request: Request,
    user_data: RegisterCustomerRequest,
    service: AuthService = Depends()
):
    """
    Customer Registration Endpoint.
    Security: Limited to 5 attempts per hour to mitigate mass-account creation bots.
    
    """

    customer = await service.register_customer(user_data.dict())

    return {
        "id": customer.id,
        "email": customer.email,
        "address": customer.address,
        "role": customer.role,
        "access_token": customer.access_token,
        "refresh": customer.refresh_token,
        "message": "Sign Up successful"
    }


@router.post("/login")
@limiter.limit("10/minute") # Protect against brute-force attacks
async def login(
    request: Request,
    login_data: LoginRequest, # Pydantic model with email and password
    service: AuthService = Depends()
):
    """
    Authenticate user and return JWT tokens.
    """
    data = await service.login(
        email=login_data.email, 
        password=login_data.password
    )
    return data

@router.post("/refresh")
async def refresh_token(
    payload: RefreshTokenRequest,
    service: AuthService = Depends()
):
    """
    Issue a new access token using a valid refresh token.
    """
    return await service.refresh_access_token(payload.refresh_token)