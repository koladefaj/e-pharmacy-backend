import uuid
from datetime import datetime

from sqlalchemy import String, Enum, DateTime, ForeignKey, func, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.enums import PrescriptionStatus

from app.db.base import Base


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # The patient/owner
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    status: Mapped[PrescriptionStatus] = mapped_column(
        Enum(PrescriptionStatus, values_callable=lambda enum: [e.value for e in enum]),
        default=PrescriptionStatus.PENDING,
        nullable=False,
        index=True
    )


    # Clinical Review
    reviewed_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


    # Relationship
    order = relationship("Order", back_populates="prescription")
    patient = relationship("User", foreign_keys=[user_id])
    pharmacist = relationship("User", foreign_keys=[reviewed_by])
