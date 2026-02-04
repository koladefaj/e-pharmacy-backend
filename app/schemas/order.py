from uuid import UUID
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class OrderListResponse(BaseModel):
    id: UUID
    status: str
    total_amount: Decimal
    requires_prescription: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
