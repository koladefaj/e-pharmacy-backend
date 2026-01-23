import logging
from uuid import UUID

from fastapi import Depends, APIRouter, BackgroundTasks
from starlette import status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.cart import CartItemCreate
from app.core.deps import get_current_customer, get_redis
from app.db.sessions import get_async_session
from app.services.cart_service import cart_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/cart",
    tags=["Customers"],
)

# -------------------------------
# ADD ITEM TO CART
# -------------------------------
@router.post("/add", status_code=status.HTTP_200_OK)
async def add_to_cart(
    item_in: CartItemCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_customer),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Add a product to the Redis-backed shopping cart.
    """
    cart = await cart_service.add_item(
        redis=redis,
        db=db,
        user_id=current_user.id,
        product_id=item_in.product_id,
        quantity=item_in.quantity,
    )

    # 🔑 Background DB sync (SAFE)
    background_tasks.add_task(
        cart_service.sync_to_db,
        user_id=current_user.id,
        items=cart["items"],
        db=db
    )

    return {"message": "Cart updated", "cart": cart}


# -------------------------------
# VIEW CART
# -------------------------------
@router.get("/cart", status_code=status.HTTP_200_OK)
async def view_cart(
    current_user: User = Depends(get_current_customer),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Retrieve the current user's cart.
    """
    return await cart_service.get_cart(redis, db, current_user.id)


# -------------------------------
# UPDATE CART ITEM
# -------------------------------
@router.patch("/cart/update", status_code=status.HTTP_200_OK)
async def update_cart_item(
    item_in: CartItemCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_customer),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Update a product quantity.
    If quantity is 0, the item is removed.
    """
    updated_cart = await cart_service.update_item(
        redis=redis,
        db=db,
        user_id=current_user.id,
        product_id=item_in.product_id,
        quantity=item_in.quantity,
    )

    # 🔑 Background DB sync (SAFE)
    background_tasks.add_task(
        cart_service.sync_to_db,
        user_id=current_user.id,
        db=db,
        items=updated_cart["items"],
    )

    return {
        "message": "Cart updated successfully",
        "cart": updated_cart,
    }


# -------------------------------
# REMOVE SINGLE ITEM
# -------------------------------
@router.delete(
    "/cart/remove/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_cart_item(
    product_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_customer),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Remove a single product from the cart.
    """
    updated_cart = await cart_service.remove_item(
        redis=redis,
        db=db,
        user_id=current_user.id,
        product_id=product_id,
    )

    background_tasks.add_task(
        cart_service.sync_to_db,
        user_id=current_user.id,
        items=updated_cart["items"],
        db=db,
    )

    # 204 → NO RESPONSE BODY
    return None


# -------------------------------
# CLEAR CART
# -------------------------------
@router.delete("/cart/clear", status_code=status.HTTP_200_OK)
async def clear_cart(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_customer),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_async_session),
):
    """
    Empty the cart completely.
    """
    await cart_service.clear_all(redis, db, current_user.id)

    background_tasks.add_task(
        cart_service.sync_to_db,
        user_id=current_user.id,
        items=[],
        db=db,
    )

    return {"message": "Cart cleared"}
