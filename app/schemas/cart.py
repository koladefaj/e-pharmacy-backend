from pydantic import BaseModel, Field
from uuid import UUID


class CartItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(..., ge=0)
