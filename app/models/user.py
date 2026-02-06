import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),  # DB-side generation
    )

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    address: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)

    hashed_password: Mapped[str] = mapped_column(String(512), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_roles",
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=False,
        default=UserRole.CUSTOMER,
        index=True,
    )

    # Pharmacist-specific (employees, not owners)
    license_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        unique=True,
    )

    license_verified: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    hired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Account state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    is_email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # Automatically updates on change
        nullable=False,
    )

    # Relationships
    cart_items = relationship(
        "CartItem", back_populates="user", cascade="all, delete-orphan"
    )
    orders = relationship(
        "Order",
        back_populates="customer",
        cascade="all, delete-orphan",
    )
