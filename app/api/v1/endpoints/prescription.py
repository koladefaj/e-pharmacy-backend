from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.db.sessions import get_async_session
from app.core.deps import get_current_user, get_current_pharmacist
from app.schemas.prescription import (
    PrescriptionApproveRequest,
    PrescriptionRejectRequest,
    PrescriptionStatusResponse,
    PendingPrescriptionResponse,
)
from app.services.prescription_service import prescription_service

router = APIRouter(
    prefix="/prescriptions",
    tags=["Prescriptions"],
)

# -------------------------------------------------
# UPLOAD PRESCRIPTION (CUSTOMER)
# -------------------------------------------------
@router.post(
    "/upload",
    response_model=PrescriptionStatusResponse,
)
async def upload_prescription(
    order_id: str,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Customer uploads a prescription for an order.
    """
    prescription = await prescription_service.upload_prescription(
        file=file,
        user_id=current_user.id,
        order_id=order_id,
        db=db,
    )

    return prescription


# -------------------------------------------------
# APPROVE PRESCRIPTION (PHARMACIST)
# -------------------------------------------------
@router.post(
    "/approve",
    response_model=PrescriptionStatusResponse,
)
async def approve_prescription(
    body: PrescriptionApproveRequest,
    pharmacist=Depends(get_current_pharmacist),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Pharmacist approves a prescription.
    """
    prescription = await prescription_service.approve(
        prescription_id=body.prescription_id,
        pharmacist_id=pharmacist.id,
        db=db,
    )

    return prescription


# -------------------------------------------------
# REJECT PRESCRIPTION (PHARMACIST)
# -------------------------------------------------
@router.post(
    "/reject",
    response_model=PrescriptionStatusResponse,
)
async def reject_prescription(
    body: PrescriptionRejectRequest,
    pharmacist=Depends(get_current_pharmacist),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Pharmacist rejects a prescription with a reason.
    """
    prescription = await prescription_service.reject(
        prescription_id=body.prescription_id,
        pharmacist_id=pharmacist.id,
        reason=body.reason,
        db=db,
    )

    return prescription

@router.get(
    "/pending",
    response_model=List[PendingPrescriptionResponse],
)
async def list_pending_prescriptions(
    pharmacist=Depends(get_current_pharmacist),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Pharmacist sees prescriptions awaiting review.
    """
    return await prescription_service.list_pending(db=db)

@router.get("/file/{prescription_id}")
async def get_prescription_file(
    prescription_id: UUID,
    pharmacist=Depends(get_current_pharmacist),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Returns a temporary URL to view/download the prescription.
    """
    url = await prescription_service.get_prescription_file_url(
        prescription_id=prescription_id,
        db=db,
    )
    return {"url": url}

