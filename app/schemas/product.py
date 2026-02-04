from pydantic import BaseModel, Field, field_validator, ConfigDict
from decimal import Decimal
from datetime import datetime, timezone
from app.db.enums import CategoryEnum
from typing import List
from uuid import UUID



# Inventory Based
class BatchBase(BaseModel):
    batch_number: str = Field(..., min_length=1, max_length=100, json_schema_extra={"example": "BN-2026-001"})
    initial_quantity: int = Field(..., gt=0, json_schema_extra={"example": "100"})
    price: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2, json_schema_extra={"example": 45.50})
    expiry_date: datetime



    @field_validator("expiry_date")
    @classmethod
    def must_be_in_future(cls, v: datetime) -> datetime:
        now = datetime.now(timezone.utc)
        # Ensure v has a timezone for comparison
        target = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if target <= now:
            raise ValueError("Expiry date must be in the future")
        return target


class BatchCreate(BatchBase):
    """
    Schema for creating a new batch. 
    Note: product_id is usually passed via the URL path, 
    but can be included here if needed.
    """
    pass

class BatchUpdate(BaseModel):
    """Schema for manual adjustments (e.g., blocking a batch)"""
    is_blocked: bool | None = None
    current_quantity: int | None = Field(None, ge=0)

class BatchRead(BatchBase):
    """Schema for returning batch data to the frontend"""
    id: UUID
    product_id: UUID
    current_quantity: int
    is_blocked: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)



# Admin Schema for Products

class ProductBase(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Amoxicillin 500mg"})
    category: CategoryEnum
    active_ingredients: str | None = None
    prescription_required: bool = False
    age_restriction: int | None = None
    storage_condition: str | None = "Store in a cool dry place"

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    # All fields optional for PATCH requests
    name: str | None = None
    is_active: bool | None = None
    prescription_required: bool | None = None

class ProductRead(BaseModel):
    id: UUID
    name: str
    category: str
    active_ingredients: str | None
    prescription_required: bool
    age_restriction: int | None
    storage_condition: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class ProductWithBatches(ProductRead):
    batches: List[BatchRead]

