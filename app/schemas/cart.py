from pydantic import BaseModel, Field
from uuid import UUID

class CartItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(..., gt=0) # Must be at least 1