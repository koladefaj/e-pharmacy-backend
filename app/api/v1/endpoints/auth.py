import logging
from fastapi import Depends, APIRouter, Request, Body
from app.models.user import User
from starlette import status
from app.schemas.user import RegisterCustomerRequest, CreatePharmacistRequest, LoginRequest, ChangePasswordRequest
from app.services.auth_service import AuthService
from app.core.deps import get_current_customer, get_allowed_password_changers, get_current_admin
from app.db.sessions import get_async_session
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
    auth_service: AuthService = Depends()
):
    """
    Customer Registration Endpoint.
    Security: Limited to 5 attempts per hour to mitigate mass-account creation bots.
    
    """

    return await auth_service.register_customer(user_data.dict())


@router.post("/pharmacist/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")  # Strict limit to prevent bot-spamming account creation
async def create_pharmacist(
    request: Request,
    user_data: CreatePharmacistRequest,
    auth_service: AuthService = Depends(),
    current_admin: User = Depends(get_current_admin)
):
    """
    Pharmacist Registration Endpoint.
    Security: Limited to 5 attempts per hour to mitigate mass-account creation bots.
    
    """

    return await auth_service.register_pharmacist(user_data.dict())

@router.post("/login")
@limiter.limit("10/minute") # Protect against brute-force attacks
async def login(
    request: Request,
    login_data: LoginRequest, # Pydantic model with email and password
    auth_service: AuthService = Depends()
):
    """
    Authenticate user and return JWT tokens.
    """
    return await auth_service.login(
        email=login_data.email, 
        password=login_data.password
    )

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    current_user: User = Depends(get_current_customer), # Dependency that gets the logged-in user
    auth_service: AuthService = Depends()
):
    """
    Deactivates the currently authenticated user's account.
    """
    await auth_service.delete_user_account(current_user.id)
    return None

@router.delete("/pharmacists/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_pharmacist(
    email: str,
    current_admin: User = Depends(get_current_admin), # Protected admin dependency
    auth_service: AuthService = Depends()
):
    """
    Admin-only: Deactivate a pharmacist account via email.
    """
    await auth_service.deactivate_pharmacist_by_email(email)
    return None

@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def update_password(
    request: Request,
    password_data: ChangePasswordRequest, 
    current_user: User = Depends(get_allowed_password_changers),
    auth_service: AuthService = Depends()
):
    """
    Allows an authenticated user to change their password.
    """
    await auth_service.change_password(
        user_id=current_user.id,
        old_password=password_data.old_password,
        new_password=password_data.new_password
    )
    return None

@router.post("/refresh")
async def refresh_token(
    payload: RefreshTokenRequest,
    auth_service: AuthService = Depends()
):
    """
    Issue a new access token using a valid refresh token.
    """
    return await auth_service.refresh_access_token(payload.refresh_token)