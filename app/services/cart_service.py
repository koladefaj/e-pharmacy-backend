from uuid import UUID
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from app.models.cart import CartItem
from app.crud.cart import CartCRUD
from app.models.inventory import InventoryBatch


class CartService:
    CART_TTL = 1209600  # 14 days

    def __init__(self, session: AsyncSession):
        self.cart_crud = CartCRUD(session)
        self.session = session

    async def get_cart(self, redis, user_id: UUID):
        """
        Retrieve cart from Redis first, fallback to DB.
        """
        # Try Redis
        items = await self.cart_crud.get_redis_items(redis, user_id)

        # If empty, try DB and repopulate Redis
        if not items:
            db_items = await self.cart_crud.get_db_items(user_id)
            if db_items:
                items = [
                    {"product_id": str(i.product_id), "quantity": i.quantity}
                    for i in db_items
                ]
                await self.cart_crud.set_redis_items(
                    redis, user_id, items, self.CART_TTL
                )

        return {
            "items": items,
            "total_items": sum(i["quantity"] for i in items),
        }

    async def add_item(
        self,
        redis,
        user_id: UUID,
        product_id: UUID,
        quantity: int,
    ):
        """
        Add an item to the cart (Redis-first).
        DB sync must be handled by the router via BackgroundTasks.
        """
        if quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quantity must be positive",
            )

        # Get existing cart to see current quantity
        cart = await self.get_cart(redis, user_id)
        items = cart["items"]

        current_qty_in_cart = next(
            (i["quantity"] for i in items if i["product_id"] == str(product_id)), 0
        )
        target_quantity = current_qty_in_cart + quantity

        # Stock validation (FEFO + timezone-safe)
        batch = await self.session.scalar(
            select(InventoryBatch)
            .where(
                InventoryBatch.product_id == product_id,
                InventoryBatch.is_blocked.is_(False),
                InventoryBatch.expiry_date > datetime.now(timezone.utc),
                InventoryBatch.current_quantity >= target_quantity,
            )
            .order_by(InventoryBatch.expiry_date.asc())
        )

        if not batch:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot add {quantity} more. Total exceeds available stock.",
            )

        # Update items list
        found = False
        for item in items:
            if item["product_id"] == str(product_id):
                item["quantity"] = target_quantity
                found = True
                break
        if not found:
            items.append({"product_id": str(product_id), "quantity": quantity})

        # Save to Redis immediately
        await self.cart_crud.set_redis_items(redis, user_id, items, self.CART_TTL)

        return {
            "items": items,
            "total_items": sum(i["quantity"] for i in items),
        }

    async def update_item(
        self,
        redis,
        user_id: UUID,
        product_id: UUID,
        quantity: int,
    ):
        """
        Update quantity of an item in the cart.
        If quantity == 0 → remove item.
        """
        cart = await self.get_cart(redis, user_id)

        if cart["total_items"] == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cart is empty"
            )

        items = cart["items"]
        updated_items = []
        found = False  # Initialize a flag

        for item in items:
            if item["product_id"] == str(product_id):
                found = True  # Mark as found
                if quantity > 0:
                    updated_items.append(
                        {"product_id": str(product_id), "quantity": quantity}
                    )
                # If quantity == 0, we simply don't append it (effectively removing it)
            else:
                updated_items.append(item)

        # Check if the item was actually in the cart
        if not found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Item not found in cart"
            )

        await self.cart_crud.set_redis_items(
            redis, user_id, updated_items, self.CART_TTL
        )

        return {
            "items": updated_items,
            "total_items": sum(i["quantity"] for i in updated_items),
        }

    async def remove_item(
        self,
        redis,
        user_id: UUID,
        product_id: UUID,
    ):
        """
        Remove a single product from the cart.
        """
        cart = await self.get_cart(redis, user_id)
        items = cart["items"]

        updated_items = [
            item for item in items if item["product_id"] != str(product_id)
        ]

        await self.cart_crud.set_redis_items(
            redis, user_id, updated_items, self.CART_TTL
        )

        return {
            "items": updated_items,
            "total_items": sum(i["quantity"] for i in updated_items),
        }

    async def sync_to_db(
        self,
        user_id: UUID,
        items: list,
    ):
        """
        Sync Redis cart to PostgreSQL.
        Must be called from router BackgroundTasks.
        """
        try:
            await self.cart_crud.clear_db_cart(user_id)

            for item in items:
                self.session.add(
                    CartItem(
                        user_id=user_id,
                        product_id=UUID(item["product_id"]),
                        quantity=item["quantity"],
                        price_at_add=0.0,
                    )
                )

            await self.session.commit()

        except Exception:
            await self.session.rollback()

    async def clear_all(self, redis, user_id: UUID):
        """
        Clear cart from Redis and DB.
        """
        await self.cart_crud.delete_redis_cart(redis, user_id)
        await self.cart_crud.clear_db_cart(user_id)
