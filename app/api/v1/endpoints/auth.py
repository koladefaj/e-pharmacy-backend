import logging
from fastapi import Depends, APIRouter, Request, BackgroundTasks
from starlette import status
from app.schemas.user import RegisterCustomerRequest, LoginRequest
from app.services.auth_service import AuthService
from app.schemas.user import RefreshTokenRequest
from app.core.deps import get_service, get_notification_service
from app.core.limiter import limiter

# Initialize logger for security and audit events
logger = logging.getLogger(__name__)

router = APIRouter( prefix="/auth", tags=["auth"],)

@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")  # Strict limit to prevent bot-spamming account creation
async def signup(
    request: Request,
    user_data: RegisterCustomerRequest,
    backgroundtasks: BackgroundTasks,
    service: AuthService = Depends(get_service(AuthService))
):
    """
    Customer Registration Endpoint.
    Security: Limited to 5 attempts per hour to mitigate mass-account creation bots.
    
    """

    return await service.register_customer(user_in=user_data.model_dump(), background_tasks=backgroundtasks)



@router.post("/login", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute") # Protect against brute-force attacks
async def login(
    request: Request,
    login_data: LoginRequest, # Pydantic model with email and password
    service: AuthService = Depends(get_service(AuthService))
):
    """
    Authenticate user and return JWT tokens.
    """
    data = await service.login(
        email=login_data.email, 
        password=login_data.password
    )
    return data

@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_token(
    payload: RefreshTokenRequest,
    service: AuthService = Depends(get_service(AuthService))
):
    """
    Issue a new access token using a valid refresh token.
    """
    return await service.refresh_access_token(payload.refresh_token)