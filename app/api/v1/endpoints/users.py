import logging

from fastapi import APIRouter, Depends, Request
from starlette import status

from app.core.deps import get_allowed_password_changers, get_service
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.user import ChangePasswordRequest
from app.services.user_service import UserService

# Initialize logger for security and audit events
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/me",
    tags=["User"],
)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def update_password(
    request: Request,
    password_data: ChangePasswordRequest,
    service: UserService = Depends(get_service(UserService)),
    current_user: User = Depends(get_allowed_password_changers),
):
    """
    Allows an authenticated user to change their password.
    """
    await service.change_password(
        user_id=current_user.id,
        old_password=password_data.old_password,
        new_password=password_data.new_password,
    )
    return None
