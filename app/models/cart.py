import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        CheckConstraint("quantity > 0"), nullable=False
    )

    price_at_add: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="cart_items")
    product = relationship("Product", back_populates="cart_items")

    # Ensure a user only has one row per product
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_user_product_cart"),
    )
