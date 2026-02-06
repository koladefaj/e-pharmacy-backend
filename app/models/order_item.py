import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    # Relationships
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Inventory (linked later during fulfillment)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory_batches.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Purchase snapshot
    quantity: Mapped[int] = mapped_column(
        CheckConstraint("quantity > 0"), nullable=False
    )

    price_at_purchase: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    # ORM relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product")
    batch = relationship("InventoryBatch")
