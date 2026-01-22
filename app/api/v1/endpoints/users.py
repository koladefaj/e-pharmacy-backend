import logging
from fastapi import Depends, APIRouter, Request, Body
from app.models.user import User
from starlette import status
from app.schemas.user import RegisterCustomerRequest, CreatePharmacistRequest, LoginRequest, ChangePasswordRequest
from app.services.user_service import UserService
from app.core.deps import get_current_customer, get_allowed_password_changers, get_current_admin
from app.db.sessions import get_async_session
from app.schemas.user import RefreshTokenRequest
from app.core.limiter import limiter

# Initialize logger for security and audit events
logger = logging.getLogger(__name__)

router = APIRouter( prefix="/me", tags=["User"],)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def update_password(
    request: Request,
    password_data: ChangePasswordRequest, 
    current_user: User = Depends(get_allowed_password_changers),
    service: UserService = Depends()
):
    """
    Allows an authenticated user to change their password.
    """
    await service.change_password(
        user_id=current_user.id,
        old_password=password_data.old_password,
        new_password=password_data.new_password
    )
    return "Password Changed"