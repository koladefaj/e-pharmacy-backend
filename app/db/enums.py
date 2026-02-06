from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"
    PHARMACIST = "pharmacist"


class OrderStatus(str, Enum):
    CREATED = "created"
    CHECKOUT_STARTED = "checkout_started"
    AWAITING_PRESCRIPTION = "awaiting_prescription"
    PRESCRIPTION_REJECTED = "prescription_rejected"
    READY_FOR_PAYMENT = "ready_for_payment"
    PAID = "paid"
    REFUNDED = "refunded"
    REFUND_PENDING = "refund_pending"
    CANCELLED = "cancelled"
    FULFILLED = "fulfilled"


class CategoryEnum(str, Enum):
    SUPPLEMENT = "supplement"
    OTC = "otc"
    MEDICAL_DEVICE = "medical_device"
    PRESCRIPTION = "prescription"


class PrescriptionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
