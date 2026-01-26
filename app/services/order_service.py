from uuid import UUID
from fastapi import HTTPException
from app.models.order import Order, OrderStatus
from app.crud.order import OrderCRUD


class OrderService:
    def __init__(self, session):
        self.order_crud = OrderCRUD(session)

    async def list_customer_orders(self, user_id: UUID):
        return await self.order_crud.get_customer_orders(user_id)

    async def get_customer_order(self, order_id: UUID) -> Order:
        order = await self.order_crud.get_by_id(order_id)

        if not order:
            raise HTTPException(404, "Order not found")

        return order

    async def cancel_order(
        self,
        *,
        order_id: UUID,
        user_id: UUID,
    ) -> Order:
        order = await self.order_crud.get_by_id(order_id)

        if not order:
            raise HTTPException(404, "Order not found")

        if order.customer_id != user_id:
            raise HTTPException(403, "Not authorized to cancel this order")

        if order.status in {
            OrderStatus.PAID,
            OrderStatus.FULFILLED,
            OrderStatus.CANCELLED,
        }:
            raise HTTPException(
                400,
                f"Order cannot be cancelled (status={order.status})",
            )

        order.status = OrderStatus.CANCELLED
        await self.order_crud.save(order)

        return order
