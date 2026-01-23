from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


# -------------------------
# BASE RESPONSE
# -------------------------
class PrescriptionStatusResponse(BaseModel):
    id: UUID
    order_id: UUID
    status: str
    reviewed_at: datetime | None = None

    class Config:
        from_attributes = True


# -------------------------
# APPROVE
# -------------------------
class PrescriptionApproveRequest(BaseModel):
    """
    Request body for approving a prescription.
    """
    prescription_id: UUID = Field(..., description="ID of the prescription to approve")


# -------------------------
# REJECT
# -------------------------
class PrescriptionRejectRequest(BaseModel):
    """
    Request body for rejecting a prescription.
    """
    prescription_id: UUID = Field(..., description="ID of the prescription to reject")
    reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Reason for rejecting the prescription",
        example="Prescription image is blurry and unreadable",
    )


class PendingPrescriptionResponse(BaseModel):
    id: UUID
    order_id: UUID
    user_id: UUID
    filename: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
