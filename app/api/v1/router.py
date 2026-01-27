from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, pharmacist, customer, cart, prescription, orders, payments
from app.api.v1.endpoints.admin import product, pharmacist as admin_pharmacist, payments as admin_payment

router = APIRouter()

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(pharmacist.router)
router.include_router(customer.router)
router.include_router(cart.router)

router.include_router(payments.router)

router.include_router(orders.router)

router.include_router(prescription.router)

router.include_router(product.router)
router.include_router(admin_pharmacist.router)
router.include_router(admin_payment.router)
