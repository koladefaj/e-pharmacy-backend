import logging
from uuid import UUID
from fastapi import HTTPException, BackgroundTasks
from app.models.order import Order, OrderStatus
from app.models.user import User
from starlette import status
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.notification.notification_service import NotificationService
from app.crud.order import OrderCRUD

logger = logging.getLogger(__name__)



class OrderService:
    def __init__(self, session: AsyncSession, notification_service: NotificationService):
        self.notification_service = notification_service
        self.order_crud = OrderCRUD(session)

    async def list_customer_orders(self, user_id: UUID):
        return await self.order_crud.get_customer_orders(user_id)

    async def get_customer_order(self, order_id: UUID) -> Order:
        order = await self.order_crud.get_by_id(order_id)

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Order not found"
            )

        return order

    async def cancel_order(
        self,
        *,
        order_id: UUID,
        user : User,
        background_tasks: BackgroundTasks
    ) -> Order:
        order = await self.order_crud.get_by_id(order_id)

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Order not found"
            )

        if order.customer_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Not authorized to cancel this order"
            )

        if order.status in {
            OrderStatus.PAID,
            OrderStatus.FULFILLED,
            OrderStatus.CANCELLED,
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order cannot be cancelled (status={order.status})",
            )

        order.status = OrderStatus.CANCELLED
        await self.order_crud.save(order)

        logger.info(f"Order {order_id} cancelled successfully.")

        background_tasks.add_task(
                self.notification_service.notify,
                email=user.email,
                phone=None,
                channels=["email"],
                message=f"Order #{str(order.id)[:8]} has been cancelled successfully"
                
            )

        return order
