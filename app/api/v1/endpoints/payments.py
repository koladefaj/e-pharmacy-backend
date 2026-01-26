import stripe
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import settings
from app.db.sessions import get_async_session, AsyncSessionLocal
from app.core.deps import get_redis
from app.models.order import Order
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


payment_service = PaymentService(stripe_api_key=settings.stripe_secret_key)

# --------------------------------------------------
# CREATE PAYMENT INTENT
# --------------------------------------------------
@router.post("/order/{order_id}")
async def create_payment_intent(
    order_id: UUID,
    db=Depends(get_async_session),
    redis=Depends(get_redis),
):
    try:
        return await payment_service.create_payment_intent(
            order_id=order_id,
            db=db,
            redis=redis,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# --------------------------------------------------
# STRIPE WEBHOOK
# --------------------------------------------------
@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    redis=Depends(get_redis),
):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig,
            settings.stripe_webhook_secret,
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    return await payment_service.handle_webhook(
        event=event.to_dict(),
        redis=redis,
        db_factory=AsyncSessionLocal,
    )


# --------------------------------------------------
# REFUND ORDER
# --------------------------------------------------
@router.post("/refund/{order_id}")
async def refund_order(
    order_id: UUID,
    amount: Decimal | None = None,
    db=Depends(get_async_session),
):
    order = await db.get(Order, order_id)

    if not order:
        raise HTTPException(404, "Order not found")

    try:
        return await payment_service.refund_order(
            order=order,
            amount=amount,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# --------------------------------------------------
# CANCEL ORDER (PRE-PAYMENT)
# --------------------------------------------------
@router.post("/cancel/{order_id}")
async def cancel_order(
    order_id: UUID,
    db=Depends(get_async_session),
):
    order = await db.get(Order, order_id)

    if not order:
        raise HTTPException(404, "Order not found")

    try:
        await payment_service.cancel_order(
            order=order,
            db=db,
        )
        return {"status": "cancelled", "order_id": order.id}
    except ValueError as e:
        raise HTTPException(400, str(e))
