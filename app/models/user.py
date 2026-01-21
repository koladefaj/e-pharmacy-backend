import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    String,
    Date,
    DateTime,
    Boolean,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.enums import user_role_enum
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    phone_number: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    address: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    date_of_birth: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        user_role_enum,
        nullable=False,
        default="customer",
    )

    # Pharmacist-specific (employees, not owners)
    license_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )

    license_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    hired_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Account state
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    
    # cart_items = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    # orders = relationship("Order",back_populates="customer",cascade="all, delete-orphan",)
