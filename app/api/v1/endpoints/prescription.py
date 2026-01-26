from fastapi import APIRouter, UploadFile, File, Depends
from uuid import UUID
from typing import List


from app.core.deps import get_current_user, get_current_pharmacist, get_service
from app.schemas.prescription import (
    PrescriptionApproveRequest,
    PrescriptionRejectRequest,
    PrescriptionStatusResponse,
    PendingPrescriptionResponse,
)
from app.services.prescription_service import PrescriptionService

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
    service: PrescriptionService = Depends(get_service(PrescriptionService)),
    current_user=Depends(get_current_user),
):
    """
    Customer uploads a prescription for an order.
    """
    prescription = await service.upload_prescription(
        file=file,
        user_id=current_user.id,
        order_id=order_id,
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
    service: PrescriptionService = Depends(get_service(PrescriptionService)),
    pharmacist=Depends(get_current_pharmacist),
):
    """
    Pharmacist approves a prescription.
    """
    prescription = await service.approve(
        prescription_id=body.prescription_id,
        pharmacist_id=pharmacist.id,
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
    service: PrescriptionService = Depends(get_service(PrescriptionService)),
):
    """
    Pharmacist rejects a prescription with a reason.
    """
    prescription = await service.reject(
        prescription_id=body.prescription_id,
        pharmacist_id=pharmacist.id,
        reason=body.reason,
    )

    return prescription

@router.get("/pending", response_model=List[PendingPrescriptionResponse])
async def list_pending_prescriptions(
    pharmacist=Depends(get_current_pharmacist),
    service: PrescriptionService = Depends(get_service(PrescriptionService)),
):
    """
    Pharmacist sees prescriptions awaiting review.
    """
    return await service.list_pending()

@router.get("/file/{prescription_id}")
async def get_prescription_file(
    prescription_id: UUID,
    service: PrescriptionService = Depends(get_service(PrescriptionService)),
    pharmacist=Depends(get_current_pharmacist),
):
    """
    Returns a temporary URL to view/download the prescription.
    """
    url = await service.get_prescription_file_url(
        prescription_id=prescription_id
    )
    return {"url": url}


# CUSTOMER: CHECK PRESCRIPTION STATUS
@router.get(
    "/{order_id}",
    response_model=PrescriptionStatusResponse,
)
async def get_prescription_status(
    order_id: UUID,
    current_user=Depends(get_current_user),
    service: PrescriptionService = Depends(get_service(PrescriptionService)),
):
    """
    Customer checks prescription status for an order.
    """
    return await service.get_status_for_customer(
        order_id=order_id,
        user_id=current_user.id,
    )


