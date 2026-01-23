from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from decimal import Decimal
from fastapi import HTTPException
import json

from app.models.order import Order
from app.models.product import Product
from app.models.order_item import OrderItem
from app.models.inventory import InventoryBatch
from app.services.cart_service import cart_service


class CheckoutService:
    CHECKOUT_TTL = 15 * 60  # 15 minutes

    async def checkout(
        self,
        *,
        user_id: UUID,
        redis,
        db: AsyncSession,
    ) -> dict:
        # --------------------------------------------------
        # 1️⃣ Load cart
        # --------------------------------------------------
        cart = await cart_service.get_cart(redis, db, user_id)

        if not cart["items"]:
            raise HTTPException(400, "Cart is empty")

        total = Decimal("0.00")
        requires_prescription = False

        # --------------------------------------------------
        # 2️⃣ Create order shell
        # --------------------------------------------------
        order = Order(
            customer_id=user_id,
            status="CHECKOUT_STARTED",
            total_amount=Decimal("0.00"),
        )
        db.add(order)
        await db.flush()  # get order.id

        # --------------------------------------------------
        # 3️⃣ Validate inventory + build order items
        # --------------------------------------------------
        for item in cart["items"]:
            product = await db.get(Product, item["product_id"])

            if not product:
                raise HTTPException(404, "Product not found")

            if product.prescription_required:
                requires_prescription = True

            batch = await db.scalar(
                select(InventoryBatch)
                .where(
                    InventoryBatch.product_id == product.id,
                    InventoryBatch.is_blocked.is_(False),
                    InventoryBatch.current_quantity > 0,
                )
                .order_by(InventoryBatch.expiry_date.asc())
            )

            if not batch:
                raise HTTPException(
                    400,
                    f"No sellable stock for {product.name}",
                )

            unit_price = batch.price
            quantity = item["quantity"]

            total += unit_price * quantity

            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    price_at_purchase=unit_price,
                )
            )

        # --------------------------------------------------
        # 4️⃣ Finalize order
        # --------------------------------------------------
        order.total_amount = total
        order.requires_prescription = requires_prescription
        order.status = (
            "AWAITING_PRESCRIPTION"
            if requires_prescription
            else "READY_FOR_PAYMENT"
        )

        await db.commit()

        # --------------------------------------------------
        # 5️⃣ Create Redis checkout session
        # --------------------------------------------------
        await redis.set(
            f"checkout:{user_id}",
            json.dumps({
                "order_id": str(order.id),
                "amount": str(total),
                "requires_prescription": requires_prescription,
            }),
            ex=self.CHECKOUT_TTL,
        )

        # --------------------------------------------------
        # 6️⃣ Response
        # --------------------------------------------------
        return {
            "order_id": order.id,
            "status": order.status,
            "expires_in": self.CHECKOUT_TTL,
            "next_step": (
                "UPLOAD_PRESCRIPTION"
                if requires_prescription
                else "PAY"
            ),
        }


checkout_service = CheckoutService()
