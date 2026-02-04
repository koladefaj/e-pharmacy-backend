import logging
from uuid import UUID

from fastapi import Depends, APIRouter, BackgroundTasks
from starlette import status
from redis.asyncio import Redis

from app.models.user import User
from app.schemas.cart import CartItemCreate
from app.core.deps import get_current_customer, get_redis, get_service
from app.services.checkout_service import CheckoutService
from app.services.cart_service import CartService


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/cart",
    tags=["Customers"],
)


# ADD ITEM TO CART
@router.post("/add", status_code=status.HTTP_200_OK)
async def add_to_cart(
    item_in: CartItemCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_customer),
    service: CartService = Depends(get_service(CartService)),
    redis: Redis = Depends(get_redis),
):
    """
    Add a product to the Redis-backed shopping cart.
    """
    cart = await service.add_item(
        redis=redis,
        user_id=current_user.id,
        product_id=item_in.product_id,
        quantity=item_in.quantity,
    )

    # Background DB sync (SAFE)
    background_tasks.add_task(
        service.sync_to_db,
        user_id=current_user.id,
        items=cart["items"],
    )

    return {"message": "Cart updated", "cart": cart}



# VIEW CART
@router.get("", status_code=status.HTTP_200_OK)
async def view_cart(
    current_user: User = Depends(get_current_customer),
    service: CartService = Depends(get_service(CartService)),
    redis: Redis = Depends(get_redis),
):
    """
    Retrieve the current user's cart.
    """
    return await service.get_cart(redis, current_user.id)



# UPDATE CART ITEM
@router.patch("/update", status_code=status.HTTP_200_OK)
async def update_cart_item(
    item_in: CartItemCreate,
    background_tasks: BackgroundTasks,
    service: CartService = Depends(get_service(CartService)),
    current_user: User = Depends(get_current_customer),
    redis: Redis = Depends(get_redis),
):
    """
    Update a product quantity.
    If quantity is 0, the item is removed.
    """
    updated_cart = await service.update_item(
        redis=redis,
        user_id=current_user.id,
        product_id=item_in.product_id,
        quantity=item_in.quantity,
    )

    # Background DB sync (SAFE)
    background_tasks.add_task(
        service.sync_to_db,
        user_id=current_user.id,
        items=updated_cart["items"],
    )

    return {
        "message": "Cart updated successfully",
        "cart": updated_cart,
    }



# REMOVE SINGLE ITEM
@router.delete(
    "/remove/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_cart_item(
    product_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_customer),
    service: CartService = Depends(get_service(CartService)),
    redis: Redis = Depends(get_redis),
):
    """
    Remove a single product from the cart.
    """
    updated_cart = await service.remove_item(
        redis=redis,
        user_id=current_user.id,
        product_id=product_id,
    )

    background_tasks.add_task(
        service.sync_to_db,
        user_id=current_user.id,
        items=updated_cart["items"],
    )

    # 204 → NO RESPONSE BODY
    return None



# CLEAR CART
@router.delete("/clear", status_code=status.HTTP_200_OK)
async def clear_cart(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_customer),
    service: CartService = Depends(get_service(CartService)),
    redis: Redis = Depends(get_redis),
):
    """
    Empty the cart completely.
    """
    await service.clear_all(redis, current_user.id)

    background_tasks.add_task(
        service.sync_to_db,
        user_id=current_user.id,
        items=[],
    )

    return {"message": "Cart cleared"}



@router.post("/checkout")
async def checkout(
    redis: Redis = Depends(get_redis),
    service: CheckoutService = Depends(get_service(CheckoutService)),
    current_user: User = Depends(get_current_customer)
):
    return await service.checkout(
        redis=redis,
        user_id=current_user.id
    )

@router.post("/resume/{order_id}")
async def resume_checkout(
    order_id: UUID,
    service: CheckoutService = Depends(get_service(CheckoutService)),
    current_user=Depends(get_current_customer),
    redis: Redis = Depends(get_redis),
):
    """
    Resume checkout after prescription approval or expired session.
    """
    return await service.resume_checkout(
        user_id=current_user.id,
        order_id=order_id,
        redis=redis,
    )
