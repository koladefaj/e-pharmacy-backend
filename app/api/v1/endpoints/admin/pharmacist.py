import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from starlette import status

from app.core.deps import get_current_admin, get_service
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.pharmacist import PharmacistApproveSchema, PharmacistRead
from app.schemas.user import CreatePharmacistRequest
from app.services.admin.pharmacist import AdminPharmacistService
from app.services.auth_service import AuthService

# Initialize logger for security and audit events
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pharmacist", tags=["Admin"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")  # Strict limit to prevent bot-spamming account creation
async def create_pharmacist(
    request: Request,
    user_data: CreatePharmacistRequest,
    backgroundtasks: BackgroundTasks,
    service: AdminPharmacistService = Depends(get_service(AdminPharmacistService)),
    current_admin: User = Depends(get_current_admin),
):
    """
    Pharmacist Registration Endpoint.
    Security: Limited to 5 attempts per hour to mitigate mass-account creation bots.

    """

    pharmacist = await service.register_pharmacist(
        user_in=user_data.model_dump(), background_tasks=backgroundtasks
    )

    logger.info(
        f"ADMIN_ACTION: Pharmacist created | "
        f"Admin: {current_admin.email} | "
        f"New Pharmacist ID: {pharmacist.id} | "
        f"RequestID: {getattr(request.state, 'request_id', 'unknown')}"
    )

    return f"Pharmacist created: {pharmacist.email}"


@router.delete("/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_pharmacist(
    email: str,
    current_admin: User = Depends(get_current_admin),
    service: AdminPharmacistService = Depends(get_service(AuthService)),
):
    """
    Admin-only: Deactivate a pharmacist account via email.
    """

    user = await service.deactivate_pharmacist_by_email(email)

    logger.info(
        f"Pharmacist account uid: {user.id} | email: {email} deactivated successfully. By {current_admin.email}"
    )
    return "Pharmacist Account Deactivated"


@router.get("/all", response_model=List[PharmacistRead])
async def list_pharmacists(
    skip: int = 0,
    limit: int = 10,
    service: AdminPharmacistService = Depends(get_service(AdminPharmacistService)),
    current_admin: User = Depends(get_current_admin),
):
    """Admin only: List all pharmacists for moderation."""
    return await service.get_pharmacist_list(skip=skip, limit=limit)


@router.patch("/{pharmacist_id}/approve", response_model=PharmacistRead)
async def approve_pharmacist(
    pharmacist_id: UUID,
    body: PharmacistApproveSchema,
    service: AdminPharmacistService = Depends(get_service(AdminPharmacistService)),
    current_admin: User = Depends(get_current_admin),
):
    """Admin only: Approve a pharmacist."""
    return await service.approve_pharmacist_account(
        pharmacist_id=pharmacist_id,
        approve_data=body,
        admin_email=current_admin.email,  # Pass admin email for logging
    )
