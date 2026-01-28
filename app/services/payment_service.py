import stripe
import logging
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from fastapi import BackgroundTasks
from app.models.order_item import OrderItem
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.cart_service import CartService
from app.services.notification.notification_service import NotificationService
from app.services.invoice_service import InvoiceService
from app.core.exceptions import InsufficientStockError

from app.models.order import Order
from app.db.enums import OrderStatus
from app.crud.product import CRUDProduct

logger = logging.getLogger(__name__)

CHECKOUT_TTL_SECONDS = 15 * 60
STRIPE_EVENT_TTL = 60 * 60 * 24


class PaymentService:

    def __init__(self, db: AsyncSession, notification_service: NotificationService):
        self.db = db
        self.notification_service = notification_service

    # CREATE PAYMENT INTENT
    async def create_payment_intent(
        self,
        *,
        order_id: UUID,
        redis,
    ) -> dict:
        order = await self.db.scalar(
            select(Order).where(Order.id == order_id)
        )

        if not order:
            raise ValueError("Order not found")

        if order.status != OrderStatus.READY_FOR_PAYMENT:
            raise ValueError("Order is not ready for payment")

        if not await redis.get(f"checkout:{order.customer_id}"):
            raise ValueError("Checkout session expired")

        # Reuse existing intent
        if order.payment_intent_id:
            try:
                intent = stripe.PaymentIntent.retrieve(order.payment_intent_id)
                return {
                    "client_secret": intent.client_secret,
                    "order_id": order.id,
                }
            except stripe.error.StripeError:
                pass

        amount_kobo = int(order.total_amount * Decimal("100"))

        intent = stripe.PaymentIntent.create(
            amount=amount_kobo,
            currency="ngn",
            metadata={
                "order_id": str(order.id),
                "customer_id": str(order.customer_id),
            },
            automatic_payment_methods={
                "enabled": True,
                "allow_redirects": "never",
            },
            idempotency_key=f"payment-order-{order.id}",
        )

        order.payment_intent_id = intent.id
        await self.db.commit()

        return {
            "client_secret": intent.client_secret,
            "order_id": order.id,
        }


    # STRIPE WEBHOOK ENTRYPOINT
    async def handle_webhook(
        self,
        *,
        event: dict,
        redis,
        db_factory,
        background_tasks: BackgroundTasks
    ) -> dict:
        event_id = event["id"]
        event_key = f"stripe:event:{event_id}"

        

        # Idempotency
        if await redis.get(event_key):
            return {"status": "duplicate"}

        await redis.set(event_key, "1", ex=STRIPE_EVENT_TTL)

        event_type = event.get("type")

        if not event_type:
            return {"status": "invalid_event"}

        data = event.get("data", {}).get("object")
        if not data:
            return {"status": "invalid_payload"}


        if event_type == "payment_intent.succeeded":
            return await self._handle_payment_succeeded(data, redis, db_factory, background_tasks)

        if event_type == "payment_intent.payment_failed":
            return await self._handle_payment_failed(data, db_factory)

        if event_type in ("charge.refunded", "charge.refund.updated"):
            return await self._handle_refund_succeeded(data, db_factory, background_tasks)

        return {"status": "ignored"}

    
    # PAYMENT SUCCEEDED
    async def _handle_payment_succeeded(
        self,
        intent,
        redis,
        db_factory,
        background_tasks: BackgroundTasks
    ) -> dict:
        
        order_id_str = intent.metadata.get("order_id")
        if not order_id_str:
            logger.warning("Stripe event missing order_id")
            return {"status": "missing_order_id"}

        order_id = UUID(order_id_str)

        async with db_factory() as db:
            order = await db.scalar(
                select(Order)
                .options(selectinload(Order.items)
                .selectinload(OrderItem.product))
                .where(Order.id == order_id)
                .with_for_update() # Locks the order row during processing
            )

            if not order or order.status == OrderStatus.PAID:
                return {"status": "already_processed"}

            # Deduct inventory
            try:
                crud_product = CRUDProduct(db)

                for item in order.items:
                    await crud_product.deduct_stock_fefo(
                        product_id=item.product_id,
                        quantity=item.quantity,
                    )


                order.status = OrderStatus.PAID
                order.paid_at = datetime.now(timezone.utc)

                await db.commit()
                logger.info("Inventory deducted for order %s", order.id)


                # Clear cart
                cart_service = CartService(db)
            
                await redis.delete(f"checkout:{order.customer_id}")
                await cart_service.clear_all(redis, order.customer_id)

                # handle notification
                user = await db.get(User, order.customer_id)

                invoice_bytes = await InvoiceService.generate_pdf_bytes(order)


                background_tasks.add_task(
                    self.notification_service.notify,
                    email=user.email,
                    phone=None,
                    message=f"Thank you for your purchase! Order #{order.id} is being processed.",
                    channels=["email"],
                    attachment=invoice_bytes.getvalue(), # Send as actual file
                    filename=f"Invoice_{order.id}.pdf"
                    
                )

                logger.info("Payment succeeded for order %s", order.id)

            except InsufficientStockError:
                logger.error(f"Stock ran out before payment webhook for Order {order.id}")
                return {"status": "out_of_stock_failure"}

            except Exception:
                await db.rollback()
                logger.exception("Payment webhook failed")
                return {"status": "error_handled"}


        return {"status": "ok"}


    # PAYMENT FAILED
    async def _handle_payment_failed(
        self,
        intent,
        db_factory,
    ) -> dict:
        order_id_str = intent.metadata.get("order_id")
        if not order_id_str:
            return {"status": "missing_order_id"}

        order_id = UUID(order_id_str)

        async with db_factory() as db:
            order = await db.get(Order, order_id)
            if order and order.status != OrderStatus.PAID:
                order.status = OrderStatus.READY_FOR_PAYMENT
                await db.commit()

        return {"status": "payment_failed"}


    # REFUND SUCCEEDED → RESTORE INVENTORY
    async def _handle_refund_succeeded(
        self,
        charge,
        db_factory,
        background_tasks: BackgroundTasks
    ) -> dict:
        payment_intent_id = charge.get("payment_intent")
        if not payment_intent_id:
            return {"status": "ignored"}

        async with db_factory() as db:
            order = await db.scalar(
                select(Order)
                .options(selectinload(Order.items))
                .where(Order.payment_intent_id == payment_intent_id)
            )

            if not order or order.status == OrderStatus.REFUNDED:
                return {"status": "already_refunded"}

            # Restore inventory
            crud_product = CRUDProduct(db)

            for item in order.items:
                await crud_product.restock_product(
                    product_id=item.product_id,
                    quantity=item.quantity,
                )

            order.status = OrderStatus.REFUNDED
            order.refunded_at = datetime.utcnow()
            await db.commit()

            user = await db.get(User, order.customer_id)


            background_tasks.add_task(
                self.notification_service.notify,
                email=user.email,
                phone=None,
                channels=["email"],
                message=f"Payment Refunded for order: #{order.id}"
                
            )

        logger.info("Refund processed for order %s", order.id)

        return {"status": "inventory_restored"}


    # MANUAL REFUND (ADMIN)
    async def refund_order(
        self,
        *,
        order: Order,
        amount: Decimal | None,
    ) -> dict:
        if order.status != OrderStatus.PAID:
            raise ValueError("Order is not refundable")

        refund = stripe.Refund.create(
            payment_intent=order.payment_intent_id,
            amount=int(amount * 100) if amount else None,
            idempotency_key=f"refund-order-{order.id}",
        )

        order.status = OrderStatus.REFUND_PENDING
        await self.db.commit()

        return {
            "refund_id": refund.id,
            "status": refund.status,
        }


    # CANCEL ORDER (PRE-PAYMENT)
    async def cancel_order(
        self,
        *,
        order: Order,
    ) -> None:
        if order.status == OrderStatus.PAID:
            raise ValueError("Paid orders must be refunded")

        if order.payment_intent_id:
            try:
                stripe.PaymentIntent.cancel(
                    order.payment_intent_id,
                    idempotency_key=f"cancel-order-{order.id}",
                )
            except stripe.error.StripeError:
                pass

        order.status = OrderStatus.CANCELLED
        await self.db.commit()

    
