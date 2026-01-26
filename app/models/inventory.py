import uuid
from sqlalchemy import String, Integer, Numeric, DateTime, ForeignKey, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
from decimal import Decimal
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db.base import Base

class InventoryBatch(Base):
    __tablename__ = "inventory_batches"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )

    product_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Stock Tracking
    batch_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True
    )

    initial_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    current_quantity: Mapped[int] = mapped_column(
        Integer, 
        nullable=False
    )
    
    # Financials
    price: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False
    ) # e.g. 99.99
    
    # Health Safety
    expiry_date: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        index=True
    )

    is_blocked: Mapped[bool] = mapped_column(
        Boolean, 
        default=False
    ) # Manual or automatic block
    
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
    )
    
    # Relationship back to the Product Master
    product = relationship("Product", back_populates="batches")