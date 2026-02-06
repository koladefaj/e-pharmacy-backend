from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_service
from app.db.sessions import get_async_session
from app.models.order import Order
from app.models.user import User
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Admin"])


# REFUND ORDER
@router.post("/refund/{order_id}")
async def refund_order(
    order_id: UUID,
    amount: Decimal | None = None,
    db: AsyncSession = Depends(get_async_session),
    service: PaymentService = Depends(get_service(PaymentService)),
    current_user: User = Depends(get_current_admin),
):
    order = await db.get(Order, order_id)

    if not order:
        raise HTTPException(404, "Order not found")

    try:
        return await service.refund_order(
            order=order,
            amount=amount,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
