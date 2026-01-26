import uuid

from sqlalchemy import Numeric, ForeignKey, DateTime, String, Boolean, func, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.db.enums import OrderStatus



class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status_enum"),
        nullable=False,
    )

    requires_prescription: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    
    payment_intent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime, 
        nullable=True
    )


    # Relationships
    customer = relationship("User", back_populates="orders")

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    prescription = relationship(
        "Prescription",
        uselist=False,
        back_populates="order",
    )
