import logging
from uuid import UUID, uuid4
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import BackgroundTasks
from app.models.order import Order
from app.models.user import User
from app.core.deps import get_storage
from sqlalchemy import select
from app.services.validation_service import validate_file_content
from app.models.prescription import Prescription
from app.db.enums import PrescriptionStatus, OrderStatus
from app.services.notification.notification_service import NotificationService

logger = logging.getLogger(__name__)

class PrescriptionService:
    def __init__(self, session: AsyncSession, notification_service: NotificationService):
        self.storage = get_storage()
        self.session = session
        self.notification_service = notification_service

    async def upload_prescription(
        self,
        *,
        file: UploadFile,
        user_id: UUID,
        order_id: UUID,
    ) -> Prescription:
        await validate_file_content(file)

        file_id = str(uuid4())
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

        self.session.add(prescription)
        await self.session.commit()
        await self.session.refresh(prescription)

        return prescription

    async def list_pending(
        self,
    ):
        result = await self.session.execute(
            select(Prescription)
            .where(Prescription.status == PrescriptionStatus.PENDING)
            .order_by(Prescription.created_at.asc())
        )
        return result.scalars().all()



    async def get_prescription_file_url(
        self,
        *,
        prescription_id: UUID,
    ):
        prescription = await self.session.get(Prescription, prescription_id)

        if not prescription:
            raise HTTPException(404, "Prescription not found")

        return self.storage.generate_presigned_url(
            prescription.file_path
        )


    async def get_status_for_customer(
        self,
        *,
        order_id: UUID,
        user_id: UUID,
    ) -> Prescription:
        """
        Fetch prescription status for a customer by order ID.
        """
        prescription = await self.session.scalar(
            select(Prescription).where(
                Prescription.order_id == order_id,
                Prescription.user_id == user_id,
            )
        )

        if not prescription:
            raise HTTPException(status_code=404, detail="Prescription not found")

        return prescription




    async def approve(
        self,
        *,
        prescription_id: UUID,
        pharmacist_id: UUID,
        background_tasks: BackgroundTasks
    ) -> Prescription:
        prescription = await self.session.get(Prescription, prescription_id)

        if not prescription:
            raise HTTPException(404, "Prescription not found")

        if prescription.status != PrescriptionStatus.PENDING:
            raise HTTPException(400, "Prescription already reviewed")

        
        prescription.status = PrescriptionStatus.APPROVED
        prescription.reviewed_by = pharmacist_id
        prescription.reviewed_at = datetime.now(timezone.utc)
        prescription.rejection_reason = None

        
        order = await self.session.get(Order, prescription.order_id)
        if not order:
            raise HTTPException(500, "Order linked to prescription not found")

        order.status = OrderStatus.READY_FOR_PAYMENT

        await self.session.commit()
        await self.session.refresh(prescription)

        user = await self.session.get(User, order.customer_id)

        background_tasks.add_task(
            self.notification_service.notify,
            email=user.email,
            phone=None,
            channels=["email"],
            message=f"Your Prescription for order: #{order.id} has been approved"
                
        )

    
        logger.info(f"Prescription {prescription_id} {prescription.status.value} by Pharmacist {pharmacist_id}")

        return prescription


    async def reject(
        self,
        *,
        prescription_id: UUID,
        pharmacist_id: UUID,
        reason: str,
        background_tasks: BackgroundTasks
    ) -> Prescription:
        prescription = await self.session.get(Prescription, prescription_id)

        if not prescription:
            raise HTTPException(404, "Prescription not found")

        if prescription.status != PrescriptionStatus.PENDING:
            raise HTTPException(400, "Prescription already reviewed")

        prescription.status = PrescriptionStatus.REJECTED
        prescription.reviewed_by = pharmacist_id
        prescription.reviewed_at = datetime.now(timezone.utc)
        prescription.rejection_reason = reason


        order = await self.session.get(Order, prescription.order_id)
        if not order:
            raise HTTPException(500, "Order linked to prescription not found")

        order.status = OrderStatus.CANCELLED

        await self.session.commit()
        await self.session.refresh(prescription)

        user = await self.session.get(User, order.customer_id)

        background_tasks.add_task(
            self.notification_service.notify,
            email=user.email,
            phone=None,
            channels=["email"],
            message=f"Your Prescription for order: #{order.id} was rejected reason: {prescription.rejection_reason}"
                
        )

        logger.info(f"Prescription {prescription_id} {prescription.status.value} by Pharmacist {pharmacist_id}")
        return prescription



