import uuid
from enum import Enum
from sqlalchemy import String, Integer, Boolean, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class CategoryEnum(str, Enum):
    SUPPLEMENT = "supplement"
    OTC = "otc"
    MEDICAL_DEVICE = "medical_device"
    PRESCRIPTION = "prescription"

class Product(Base):
    __tablename__ = "products"

    id:  Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    category: Mapped[CategoryEnum] = mapped_column(
        SAEnum(CategoryEnum),
        nullable=False,
        index=True,
        
    )  # supplement / OTC / medical device
    
    # Clinical / Regulatory Info
    active_ingredients: Mapped[str] = mapped_column(
        Text, 
        nullable=True
    )

    prescription_required: Mapped[bool] = mapped_column(
        Boolean, 
        default=False
        
    )

    age_restriction: Mapped[int] = mapped_column(
        Integer, 
        nullable=True
        
    )  # e.g., 18 for certain meds

    storage_condition: Mapped [str] = mapped_column(
        String(255), 
        nullable=True
    )  # e.g., "Store below 25°C"
    
    # Status
    is_active: Mapped [bool] = mapped_column(
        Boolean, 
        default=True
    )  # Admin can hide product globally

    batches = relationship("InventoryBatch", back_populates="product", cascade="all, delete-orphan")


    # Inside Product model
    # cart_items = relationship("CartItem", back_populates="product")