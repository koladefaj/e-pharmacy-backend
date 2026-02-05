import stripe
from redis import Redis
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.sessions import get_async_session
from app.core.deps import get_redis, get_current_customer, get_service, get_session_factory
from app.models.user import User
from app.models.order import Order
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])




# CREATE PAYMENT INTENT
@router.post("/order/{order_id}")
async def create_payment_intent(
    order_id: UUID,
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_customer),
    service: PaymentService = Depends(get_service(PaymentService))
):
    try:
        return await service.create_payment_intent(
            order_id=order_id,
            redis=redis,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# STRIPE WEBHOOK
@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db_factory = Depends(get_session_factory),
    redis: Redis = Depends(get_redis),
    service: PaymentService = Depends(get_service(PaymentService))
    
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
    

    return await service.handle_webhook(
        event=event,
        redis=redis,
        db_factory=db_factory,
        background_tasks=background_tasks,
    )



# CANCEL ORDER (PRE-PAYMENT)
@router.post("/cancel/{order_id}")
async def cancel_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_customer),
    service: PaymentService = Depends(get_service(PaymentService))
):
    order = await db.get(Order, order_id)

    if not order:
        raise HTTPException(404, "Order not found")

    try:
        await service.cancel_order(
            order=order,
        )
        return {"status": "cancelled", "order_id": order.id}
    except ValueError as e:
        raise HTTPException(400, str(e))
