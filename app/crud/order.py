from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderStatus


class OrderCRUD:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, order_id: UUID) -> Order | None:
        return await self.session.get(Order, order_id)

    async def get_customer_orders(self, customer_id: UUID):
        result = await self.session.execute(
            select(Order)
            .where(Order.customer_id == customer_id)
            .order_by(Order.created_at.desc())
        )
        return result.scalars().all()

    async def get_active_order(self, customer_id: UUID) -> Order | None:
        result = await self.session.execute(
            select(Order)
            .where(
                Order.customer_id == customer_id,
                Order.status.in_(
                    [
                        OrderStatus.CHECKOUT_STARTED,
                        OrderStatus.AWAITING_PRESCRIPTION,
                        OrderStatus.READY_FOR_PAYMENT,
                    ]
                ),
            )
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def save(self, order: Order) -> None:
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
