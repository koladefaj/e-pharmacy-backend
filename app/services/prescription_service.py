from uuid import UUID
import uuid
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_storage
from sqlalchemy import select
from app.services.validation_service import validate_file_content
from app.models.prescription import Prescription, PrescriptionStatus


class PrescriptionService:
    def __init__(self):
        self.storage = get_storage()

    async def upload_prescription(
        self,
        *,
        file: UploadFile,
        user_id: UUID,
        order_id: UUID,
        db: AsyncSession,
    ) -> Prescription:
        await validate_file_content(file)

        file_id = str(uuid.uuid4())
        ext = "." + file.filename.split(".")[-1].lower()
        storage_key = f"prescriptions/{file_id}{ext}"

        file_bytes = await file.read()
        await self.storage.upload(
            file_id=storage_key,
            file_name=file.filename,
            file_bytes=file_bytes,
            content_type=file.content_type,
        )

        prescription = Prescription(
            user_id=user_id,
            order_id=order_id,
            file_path=storage_key,
            filename=file.filename,
            status=PrescriptionStatus.PENDING,
        )

        db.add(prescription)
        await db.commit()
        await db.refresh(prescription)

        return prescription

    async def list_pending(
        self,
        db: AsyncSession,
    ):
        result = await db.execute(
            select(Prescription)
            .where(Prescription.status == PrescriptionStatus.PENDING)
            .order_by(Prescription.created_at.asc())
        )
        return result.scalars().all()

        

    async def get_prescription_file_url(
        self,
        *,
        prescription_id: UUID,
        db: AsyncSession,
    ):
        prescription = await db.get(Prescription, prescription_id)

        if not prescription:
            raise HTTPException(404, "Prescription not found")

        return self.storage.generate_presigned_url(
            prescription.file_path
        )



    async def approve(
        self,
        *,
        prescription_id: UUID,
        pharmacist_id: UUID,
        db: AsyncSession,
    ) -> Prescription:
        prescription = await db.get(Prescription, prescription_id)

        if not prescription:
            raise HTTPException(404, "Prescription not found")

        if prescription.status != PrescriptionStatus.PENDING:
            raise HTTPException(400, "Prescription already reviewed")

        prescription.status = PrescriptionStatus.APPROVED
        prescription.reviewed_by = pharmacist_id
        prescription.reviewed_at = datetime.now(timezone.utc)
        prescription.rejection_reason = None

        await db.commit()
        await db.refresh(prescription)

        return prescription

    async def reject(
        self,
        *,
        prescription_id: UUID,
        pharmacist_id: UUID,
        reason: str,
        db: AsyncSession,
    ) -> Prescription:
        prescription = await db.get(Prescription, prescription_id)

        if not prescription:
            raise HTTPException(404, "Prescription not found")

        if prescription.status != PrescriptionStatus.PENDING:
            raise HTTPException(400, "Prescription already reviewed")

        prescription.status = PrescriptionStatus.REJECTED
        prescription.reviewed_by = pharmacist_id
        prescription.reviewed_at = datetime.now(timezone.utc)
        prescription.rejection_reason = reason

        await db.commit()
        await db.refresh(prescription)

        return prescription


prescription_service = PrescriptionService()
