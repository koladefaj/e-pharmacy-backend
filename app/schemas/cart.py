from uuid import UUID

from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(..., ge=0)
