import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InventoryBatch(Base):
    __tablename__ = "inventory_batches"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    product_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Stock Tracking
    batch_number: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )

    initial_quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    current_quantity: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("current_quantity >= 0"),  # Prevent overselling
        nullable=False,
    )

    # Financials
    price: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2), nullable=False
    )  # e.g. 99.99

    # Health Safety
    expiry_date: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    is_blocked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # Manual or automatic block

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint("product_id", "batch_number", name="uq_product_batch"),
        CheckConstraint(
            "current_quantity <= initial_quantity", name="check_stock_limit"
        ),
    )

    # Relationship back to the Product Master
    product = relationship("Product", back_populates="batches")
