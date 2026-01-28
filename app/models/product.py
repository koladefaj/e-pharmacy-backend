import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, Text, Enum, CheckConstraint, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.db.enums import CategoryEnum




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
        nullable=False,
    )

    # supplement / OTC / medical device
    category: Mapped[CategoryEnum] = mapped_column(
        Enum(CategoryEnum, values_callable=lambda enum: [e.value for e in enum]),
        nullable=False,
        index=True,
        
    )
    
    # Clinical / Regulatory Info
    active_ingredients: Mapped[str | None]  = mapped_column(
        Text, 
        nullable=True
    )

    storage_condition: Mapped [str | None] = mapped_column(
        String(255), 
        nullable=True
    )  # e.g., "Store below 25°C"
    

    # Regulatory details
    prescription_required: Mapped[bool] = mapped_column(
        Boolean, 
        default=False
        
    )

    age_restriction: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint('age_restriction >= 0'), 
        nullable=True
        
    )  # e.g., 18 for certain meds

    # Status
    is_active: Mapped [bool] = mapped_column(
        Boolean, 
        default=True
    )  # Admin can hide product globally

    # Tracking
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    batches = relationship("InventoryBatch", back_populates="product", cascade="all, delete-orphan")
    cart_items = relationship("CartItem", back_populates="product")