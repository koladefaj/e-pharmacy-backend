import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from decimal import Decimal
from fastapi import HTTPException
from app.models.order import Order
from app.db.enums import OrderStatus
from app.models.product import Product
from app.models.order_item import OrderItem
from app.models.inventory import InventoryBatch
from app.services.cart_service import CartService
from app.crud.order import OrderCRUD


class CheckoutService:
    CHECKOUT_TTL = 15 * 60  # 15 minutes

    def __init__(self, session: AsyncSession):
        self.order_crud = OrderCRUD(session)
        self.cart_service = CartService(session)
        self.session = session


    async def checkout(
        self,
        *,
        user_id: UUID,
        redis,
    ) -> dict:
        # --------------------------------------------------
        # 1️⃣ Load cart
        # --------------------------------------------------
        existing_order = await self.order_crud.get_active_order(user_id)

        if existing_order:
            raise HTTPException(
                400,
                "You already have an active order. Please complete or cancel it.",
            )

        cart = await self.cart_service.get_cart(redis, user_id)

        if not cart["items"]:
            raise HTTPException(400, "Cart is empty")

        total = Decimal("0.00")
        requires_prescription = False

        # --------------------------------------------------
        # 2️⃣ Create order shell
        # --------------------------------------------------
        order = Order(
            customer_id=user_id,
            status=OrderStatus.CHECKOUT_STARTED,
            total_amount=Decimal("0.00"),
        )
        self.session.add(order)
        await self.session.flush()  # get order.id

        # --------------------------------------------------
        # 3️⃣ Validate inventory + build order items
        # --------------------------------------------------
        for item in cart["items"]:
            product = await self.session.get(Product, item["product_id"])

            if not product:
                raise HTTPException(404, "Product not found")

            if product.prescription_required:
                requires_prescription = True

            batch = await self.session.scalar(
                select(InventoryBatch)
                .where(
                    InventoryBatch.product_id == product.id,
                    InventoryBatch.is_blocked.is_(False),
                    InventoryBatch.current_quantity >= 0,
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

            self.session.add(
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
            OrderStatus.AWAITING_PRESCRIPTION
            if requires_prescription
            else OrderStatus.READY_FOR_PAYMENT
        )

        await self.session.commit()

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

        await self.cart_service.clear_all(redis, user_id)



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

    async def resume_checkout(
        self,
        *,
        user_id: UUID,
        order_id: UUID,
        redis,
    ) -> dict:
        # 1️⃣ Fetch order
        order = await self.order_crud.get_by_id(order_id)


        if not order:
            raise HTTPException(404, "Order not found")

        if order.customer_id != user_id:
            raise HTTPException(403, "Not authorized to resume this order")

        if order.status != OrderStatus.READY_FOR_PAYMENT:
            raise HTTPException(
                400,
                f"Order cannot be resumed (status={order.status})"
            )

        # 2️⃣ Create fresh Redis checkout session
        await redis.set(
            f"checkout:{user_id}",
            json.dumps({
                "order_id": str(order.id),
                "amount": str(order.total_amount),
                "requires_prescription": order.requires_prescription,
            }),
            ex=self.CHECKOUT_TTL,
        )

        # 3️⃣ Response
        return {
            "order_id": order.id,
            "status": order.status,
            "expires_in": self.CHECKOUT_TTL,
            "next_step": "PAY",
        }



