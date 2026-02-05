from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.db.enums import PrescriptionStatus


# BASE RESPOONSE
class PrescriptionBaseResponse(BaseModel):

    id: UUID
    order_id: UUID
    status: PrescriptionStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrescriptionStatusResponse(PrescriptionBaseResponse):
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None


# APPROVE
class PrescriptionApproveRequest(BaseModel):
    """
    Request body for approving a prescription.
    """
    prescription_id: UUID = Field(..., description="ID of the prescription to approve")



# REJECT
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
        json_schema_extra={"example": "Prescription image is blurry and unreadable"},
    )


class PendingPrescriptionResponse(BaseModel):
    id: UUID
    order_id: UUID
    user_id: UUID
    filename: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)