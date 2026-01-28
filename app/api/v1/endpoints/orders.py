from fastapi import APIRouter, Depends, BackgroundTasks
from uuid import UUID
from app.core.deps import get_current_customer, get_service, get_notification_service
from app.models.user import User
from app.schemas.order import OrderListResponse
from app.services.order_service import OrderService

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)


# LIST CUSTOMER ORDERS
@router.get("",response_model=list[OrderListResponse])
async def list_orders(
    current_user: User =Depends(get_current_customer),
    service: OrderService = Depends(get_service(OrderService))
):
    """
    Customer lists their orders.
    """
    return await service.list_customer_orders(
        user_id=current_user.id,
    )

@router.post("/{order_id}/cancel", response_model=OrderListResponse)
async def cancel_order(
    order_id: UUID,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_customer),
    service: OrderService = Depends(get_service(OrderService)),
):

    return await service.cancel_order(
        order_id=order_id,
        user = current_user,
        background_tasks=background_tasks
    )