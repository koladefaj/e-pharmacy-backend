# class EmailService:
#     async def send_prescription_approved(
#         self,
#         *,
#         to_email: str,
#         order_id,
#     ):
#         # Stub implementation (GitHub-safe)
#         print(
#             f"[EMAIL] To: {to_email} | "
#             f"Your prescription for order {order_id} was APPROVED"
#         )

#     async def send_prescription_rejected(
#         self,
#         *,
#         to_email: str,
#         order_id,
#         reason: str,
#     ):
#         print(
#             f"[EMAIL] To: {to_email} | "
#             f"Your prescription for order {order_id} was REJECTED. "
#             f"Reason: {reason}"
#         )


# email_service = EmailService()

# from app.services.email_service import email_service

# async def approve(...):
#     ...

#     prescription.status = PrescriptionStatus.APPROVED
#     prescription.reviewed_by = pharmacist_id
#     prescription.reviewed_at = datetime.utcnow()

#     await db.commit()
#     await db.refresh(prescription)

#     # 📧 Notify customer (non-blocking)
#     await email_service.send_prescription_approved(
#         to_email=prescription.user.email,
#         order_id=prescription.order_id,
#     )

#     return prescription

# async def reject(...):
#     ...

#     prescription.status = PrescriptionStatus.REJECTED
#     prescription.reviewed_by = pharmacist_id
#     prescription.reviewed_at = datetime.utcnow()
#     prescription.rejection_reason = reason

#     await db.commit()
#     await db.refresh(prescription)

#     # 📧 Notify customer
#     await email_service.send_prescription_rejected(
#         to_email=prescription.user.email,
#         order_id=prescription.order_id,
#         reason=reason,
#     )

#     return prescription

# background_tasks.add_task(
#     email_service.send_prescription_approved,
#     to_email=prescription.user.email,
#     order_id=prescription.order_id,
# )
